// Phone app: connect, show the live screen, talk, listen.  (Owner: Phone app)
// Message contract: see CLAUDE.md "How the parts talk to each other".

const $ = (id) => document.getElementById(id);
let ws = null;
let lastFrameUrl = null;

// ---------------------------------------------------------------- connect
$("callBtn").onclick = () => connect($("code").value.trim());
$("code").addEventListener("keydown", (e) => { if (e.key === "Enter") $("callBtn").click(); });

function connect(code) {
  if (code.length !== 6) { $("connectError").textContent = "The code has 6 digits."; return; }
  $("connectError").textContent = "";
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.binaryType = "blob";
  ws.onopen = () => ws.send(JSON.stringify({ type: "hello", code }));
  ws.onmessage = (e) => (e.data instanceof Blob ? showFrame(e.data) : handle(JSON.parse(e.data)));
  ws.onclose = () => { showScreen("connect"); $("connectError").textContent = "Call ended."; };
  ws.onerror = () => { $("connectError").textContent = "Could not reach the PC."; };
}

function send(obj) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); }
function showScreen(name) { $("connect").classList.toggle("hidden", name !== "connect"); $("call").classList.toggle("hidden", name !== "call"); }

// ------------------------------------------------------------- messages
function handle(msg) {
  switch (msg.type) {
    case "welcome": showScreen("call"); setStatus(msg.text); break;
    case "status": setStatus(msg.text); break;
    case "reply": addMsg(msg.text, "pc"); speak(msg.text); setStatus(""); break;
    case "file": addFile(msg.name, msg.url); break;
    case "confirm": askConfirm(msg.id, msg.text); break;
    case "error": addMsg("Error: " + msg.text, "pc"); $("connectError").textContent = msg.text; break;
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
$("hangupBtn").onclick = () => { send({ type: "hangup" }); if (ws) ws.close(); };

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
