# HomeCall Windows helper.  (Owner: Hands)  Started once by pc/actions/uia.py and kept running,
# so each question takes milliseconds instead of starting PowerShell every time (1-2 s).
# Reads one JSON request per line on stdin, writes one JSON answer per line on stdout.
#   {"op":"at","x":100,"y":200}          -> what is at this screen point (real pixels)
#   {"op":"find","hwnd":123,"text":"Send"} -> visible named controls in that window that contain the text
#   {"op":"volume_get"} / {"op":"volume_set","level":0.5} -> master volume, 0.0 - 1.0
# It only READS the screen and sets the volume; it never clicks or types.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, WindowsBase
$A = [System.Windows.Automation.AutomationElement]
$S = [System.Windows.Automation.TreeScope]
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$audioLoaded = $false

function Describe($e) {
  $proc = ''
  try { $proc = (Get-Process -Id $e.Current.ProcessId).ProcessName } catch {}
  $r = $e.Current.BoundingRectangle
  return @{ name = $e.Current.Name; control = $e.Current.ControlType.ProgrammaticName; process = $proc;
            x = [int]($r.X + $r.Width / 2); y = [int]($r.Y + $r.Height / 2); enabled = $e.Current.IsEnabled }
}

function Load-Audio {
  Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {
  int f(); int g(); int h(); int i();
  int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext);
  int j();
  int GetMasterVolumeLevelScalar(out float pfLevel);
  int k(); int l(); int m(); int n();
  int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, Guid pguidEventContext);
  int GetMute(out bool pbMute);
}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice { int Activate(ref Guid id, int clsCtx, int activationParams, out IAudioEndpointVolume aev); }
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator { int f(); int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint); }
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumeratorComObject { }
public class HomeCallAudio {
  static IAudioEndpointVolume Vol() {
    var enumerator = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator;
    IMMDevice dev = null; Marshal.ThrowExceptionForHR(enumerator.GetDefaultAudioEndpoint(0, 1, out dev));
    IAudioEndpointVolume epv = null; var epvid = typeof(IAudioEndpointVolume).GUID;
    Marshal.ThrowExceptionForHR(dev.Activate(ref epvid, 23, 0, out epv)); return epv;
  }
  public static float Volume {
    get { float v = -1; Marshal.ThrowExceptionForHR(Vol().GetMasterVolumeLevelScalar(out v)); return v; }
    set { Marshal.ThrowExceptionForHR(Vol().SetMasterVolumeLevelScalar(value, Guid.Empty)); }
  }
  public static bool Mute {
    get { bool m; Marshal.ThrowExceptionForHR(Vol().GetMute(out m)); return m; }
    set { Marshal.ThrowExceptionForHR(Vol().SetMute(value, Guid.Empty)); }
  }
}
'@
  $script:audioLoaded = $true
}

$wanted = @('ControlType.Button', 'ControlType.Hyperlink', 'ControlType.MenuItem', 'ControlType.ListItem',
            'ControlType.TabItem', 'ControlType.CheckBox', 'ControlType.RadioButton', 'ControlType.SplitButton',
            'ControlType.TreeItem', 'ControlType.DataItem')
$skip = @('ControlType.Window', 'ControlType.TitleBar', 'ControlType.Document', 'ControlType.ScrollBar',
          'ControlType.MenuBar', 'ControlType.ToolBar', 'ControlType.StatusBar')

while ($true) {
  $line = [Console]::In.ReadLine()
  if ($line -eq $null) { break }
  try {
    $req = $line | ConvertFrom-Json
    switch ($req.op) {
      'at' {
        $e = $A::FromPoint((New-Object System.Windows.Point([double]$req.x, [double]$req.y)))
        # In Explorer's details view the point may be on a cell ("Date modified"): use its row (ListItem).
        $up = $e
        for ($i = 0; $i -lt 4 -and $up; $i++) {
          if ($up.Current.ControlType.ProgrammaticName -eq 'ControlType.ListItem') { $e = $up; break }
          $up = $walker.GetParent($up)
        }
        $out = Describe $e
      }
      'find' {
        $win = $A::FromHandle([IntPtr][long]$req.hwnd)
        $cond = New-Object System.Windows.Automation.PropertyCondition($A::IsOffscreenProperty, $false)
        $needle = ([string]$req.text).ToLower()
        $best = @(); $other = @()
        foreach ($e in $win.FindAll($S::Descendants, $cond)) {
          $n = $e.Current.Name
          if (-not $n -or -not $n.ToLower().Contains($needle)) { continue }
          $ct = $e.Current.ControlType.ProgrammaticName
          if ($skip -contains $ct) { continue }   # whole windows, title bars, web pages: not something to click
          $d = Describe $e
          # Real buttons/links first; but some apps show buttons as plain "Pane"/"Text", so keep those too.
          if ($wanted -contains $ct) { $d.preferred = $true; $best += $d } else { $d.preferred = $false; $other += $d }
          if ($best.Count + $other.Count -ge 60) { break }
        }
        $out = @{ hits = @($best + $other | Select-Object -First 30); window = $win.Current.Name }
      }
      'volume_get' { if (-not $audioLoaded) { Load-Audio }; $out = @{ level = [HomeCallAudio]::Volume; muted = [HomeCallAudio]::Mute } }
      'volume_set' {
        if (-not $audioLoaded) { Load-Audio }
        [HomeCallAudio]::Volume = [float]$req.level
        if ($req.PSObject.Properties.Name -contains 'mute') { [HomeCallAudio]::Mute = [bool]$req.mute }
        elseif ([HomeCallAudio]::Mute) { [HomeCallAudio]::Mute = $false }
        $out = @{ level = [HomeCallAudio]::Volume; muted = [HomeCallAudio]::Mute }
      }
      default { $out = @{ error = "unknown op" } }
    }
  } catch {
    $out = @{ error = $_.Exception.Message }
  }
  [Console]::Out.WriteLine(($out | ConvertTo-Json -Compress -Depth 4))
  [Console]::Out.Flush()
}
