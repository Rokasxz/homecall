// Phone app: connect, show the live screen, talk, listen.  (Owner: Phone app)
// Message contract: see CLAUDE.md "How the parts talk to each other".

const $ = (id) => document.getElementById(id);
let ws = null;
let lastFrameUrl = null;

// ---------------------------------------------------------------- connect
$("callBtn").onclick = () => connect($("code").value.trim());
$("code").addEventListener("keydown", (e) => { if (e.key === "Enter") $("callBtn").click(); });

// Two ways to talk: "Type" stays here; "Voice call" opens the voice page with the same code.
// The code is kept for this tab only (sessionStorage), never in the address.
const CODE_KEY = "homecallCode";
function rememberCode(code) { try { sessionStorage.setItem(CODE_KEY, code); } catch (_) {} }
try { const saved = sessionStorage.getItem(CODE_KEY); if (saved) $("code").value = saved; } catch (_) {}

// Scanned the QR code on the PC? It opens this page with "#code=123456" (after the "#",
// so it never goes to any server). Fill it in and take it out of the address bar.
const fromQr = location.hash.match(/code=(\d{6})/);
if (fromQr) {
  $("code").value = fromQr[1];
  rememberCode(fromQr[1]);
  history.replaceState(null, "", location.pathname);
}
$("voiceBtn").onclick = () => {
  const code = $("code").value.trim();
  if (code.length !== 6) { $("connectError").textContent = "The code has 6 digits."; return; }
  rememberCode(code);
  location.href = "/voice/call";
};

// The call reconnects by itself if the connection drops (phone locked, network
// switch, server restart). It stops at the first "error" from the PC (wrong code,
// another phone on the call), so it never burns through the wrong-code lockout.
let callCode = null;     // the code of the current call, for reconnecting
let wantCall = false;    // false after Hang up or an error from the PC
let connected = false;   // the PC said "welcome" in this call: only then reconnect by itself
let retries = 0;
let busyTries = 0;       // reconnect refused because the PC still holds the old, dead connection
const pending = [];      // things said while disconnected, sent after reconnecting
const NO_REACH = "Can't reach your PC. Open the newest address (it changes when the PC restarts) " +
                 "and check HomeCall still runs on the PC. Still stuck? Switch between Wi-Fi and mobile data.";

function connect(code) {
  if (code.length !== 6) { $("connectError").textContent = "The code has 6 digits."; return; }
  $("connectError").textContent = "";
  callCode = code; wantCall = true; connected = false; retries = 0; busyTries = 0;
  rememberCode(code);
  calling(true);
  open();
}

// Show right away that the tap did something; back to normal when it ends.
function calling(on) {
  const title = $("callBtn").querySelector(".choice-title");
  $("callBtn").disabled = on; $("voiceBtn").disabled = on;
  title.textContent = on ? "Calling your PC..." : title.dataset.label;
}

function open() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const sock = new WebSocket(`${proto}://${location.host}/ws`);
  ws = sock;
  sock.binaryType = "arraybuffer";
  sock.onopen = () => sock.send(JSON.stringify({ type: "hello", code: callCode }));
  sock.onmessage = (e) => (e.data instanceof ArrayBuffer
    ? showFrame(new Blob([e.data], { type: "image/jpeg" }))  // a type helps iPhone Safari show it
    : handle(JSON.parse(e.data)));
  // Some networks never answer: give up after 10 s instead of waiting forever.
  setTimeout(() => { if (sock.readyState === WebSocket.CONNECTING) sock.close(); }, 10000);
  sock.onclose = () => {
    if (wantCall && connected && busyTries > 0 && busyTries <= 15) {
      setStatus("Reconnecting... (the PC is closing the old connection)");
      setTimeout(open, 3000);  // the PC frees a dead connection within ~20 s: keep trying up to 45 s
    } else if (wantCall && connected && retries < 5) {
      retries += 1;
      setStatus("Connection lost, reconnecting...");
      setTimeout(open, 1500);
    } else {
      calling(false);
      showScreen("connect");
      if (!$("connectError").textContent) $("connectError").textContent = connected ? "Call ended." : NO_REACH;
    }
  };
  ws.onerror = () => { if (!wantCall) $("connectError").textContent = "Could not reach the PC."; };
}

function send(obj) {
  if (ws && ws.readyState === 1) { ws.send(JSON.stringify(obj)); return; }
  pending.push(obj);  // never drop what the user said: send it once we're back
  setStatus(wantCall ? "Reconnecting... I'll send it when we're back." : "Not connected. Call your PC first.");
}

function showScreen(name) { $("connect").classList.toggle("hidden", name !== "connect"); $("call").classList.toggle("hidden", name !== "call"); }

// ------------------------------------------------------------- messages
function handle(msg) {
  switch (msg.type) {
    case "welcome":
      connected = true; calling(false); busyTries = 0;
      showScreen("call"); setStatus(msg.text); retries = 0;
      while (pending.length) send(pending.shift());
      break;
    case "status": setStatus(msg.text); break;
    case "reply": addMsg(msg.text, "pc"); speak(msg.text); setStatus(""); break;
    case "file": addFile(msg.name, msg.url); break;
    case "confirm": askConfirm(msg.id, msg.text); break;
    case "error": {
      if (connected && wantCall && /already on a call/i.test(msg.text) && busyTries < 15) {
        busyTries += 1;  // our own old connection, not freed yet: onclose tries again shortly
        break;
      }
      const restarted = retries > 0 && /pairing code/i.test(msg.text);  // reconnect with an old code
      const text = restarted ? "The PC was restarted: enter the new code shown on the PC." : msg.text;
      wantCall = false; addMsg(text, "pc"); $("connectError").textContent = text; showScreen("connect");
      break;
    }
  }
}

function showFrame(blob) {
  const url = URL.createObjectURL(blob);
  $("screen").src = url;
  if (lastFrameUrl) URL.revokeObjectURL(lastFrameUrl);
  lastFrameUrl = url;
}

function setStatus(text) { $("status").textContent = text || ""; }

function addMsg(text, who) {
  const div = document.createElement("div");
  div.className = "msg " + who;
  div.textContent = text;
  $("log").appendChild(div);
  $("log").scrollTop = $("log").scrollHeight;
}

function addFile(name, url) {
  const div = document.createElement("div");
  div.className = "msg pc file";
  const a = document.createElement("a");
  a.href = url; a.textContent = "Download " + name; a.setAttribute("download", name);
  div.append("File from your PC: ", a);
  $("log").appendChild(div);
  $("log").scrollTop = $("log").scrollHeight;
}

function askConfirm(id, text) {
  $("confirmText").textContent = text;
  $("confirmBox").classList.remove("hidden");
  $("yesBtn").onclick = () => { send({ type: "confirm", id, ok: true }); $("confirmBox").classList.add("hidden"); };
  $("noBtn").onclick = () => { send({ type: "confirm", id, ok: false }); $("confirmBox").classList.add("hidden"); };
}

// ---------------------------------------------------------------- saying
function say(text) {
  text = text.trim();
  if (!text) return;
  addMsg(text, "me");
  setStatus("Sending...");
  send({ type: "say", text });
}

$("textForm").onsubmit = (e) => { e.preventDefault(); say($("textInput").value); $("textInput").value = ""; };
$("hangupBtn").onclick = () => {
  wantCall = false; pending.length = 0;
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: "hangup" }));  // never queue it for a later call
  if (ws) ws.close();
};

// ----------------------------------------------------------------- voice
// Speech-to-text: the browser's built-in recognizer (Chrome on Android, Safari on iOS).
// Needs https (or localhost). If unavailable, the mic button hides and typing still works.
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SR) {
  $("micBtn").classList.add("hidden");
} else {
  let rec = null;
  const start = (e) => {
    e.preventDefault();
    rec = new SR();
    rec.lang = navigator.language || "en-US";
    rec.interimResults = false;
    rec.onresult = (ev) => say(ev.results[0][0].transcript);
    rec.onerror = (ev) => setStatus("Mic error: " + ev.error);
    rec.onend = () => $("micBtn").classList.remove("listening");
    $("micBtn").classList.add("listening");
    setStatus("Listening...");
    rec.start();
  };
  const stop = () => { if (rec) rec.stop(); };
  $("micBtn").addEventListener("pointerdown", start);
  $("micBtn").addEventListener("pointerup", stop);
  $("micBtn").addEventListener("pointercancel", stop);
}

// Text-to-speech: the browser reads the PC's replies aloud.
function speak(text) {
  if (!("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}
