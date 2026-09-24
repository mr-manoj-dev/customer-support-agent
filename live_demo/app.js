/**
 * Apex Commerce AI Voice Customer Support Desk Frontend
 * Handles Gemini 3.8 Live WebSocket connection, microphone audio capture (16kHz PCM),
 * audio playback (24kHz PCM), live camera vision frames (1 FPS), and reactive UI state.
 */

// UI Element Selectors
const customerSelect = document.querySelector("#customerSelect");
const orderSelect = document.querySelector("#orderSelect");
const systemModelLabel = document.querySelector("#systemModelLabel");
const callStatusPill = document.querySelector("#callStatusPill");
const callStatusText = document.querySelector("#callStatusText");
const waveform = document.querySelector("#waveform");
const micBtn = document.querySelector("#micBtn");
const micBtnLabel = document.querySelector("#micBtnLabel");
const cameraBtn = document.querySelector("#cameraBtn");
const resetSessionBtn = document.querySelector("#resetSessionBtn");
const cameraStage = document.querySelector("#cameraStage");
const cameraVideo = document.querySelector("#cameraVideo");
const captureCanvas = document.querySelector("#captureCanvas");
const transcriptFeed = document.querySelector("#transcriptFeed");
const turnCounter = document.querySelector("#turnCounter");
const chatForm = document.querySelector("#chatForm");
const chatInput = document.querySelector("#chatInput");
const demoScenariosList = document.querySelector("#demoScenariosList");

// Customer & Order Card Selectors
const customerAvatar = document.querySelector("#customerAvatar");
const customerName = document.querySelector("#customerName");
const customerLoyalty = document.querySelector("#customerLoyalty");
const customerEmail = document.querySelector("#customerEmail");
const customerPhone = document.querySelector("#customerPhone");
const customerAddress = document.querySelector("#customerAddress");
const orderStatusBadge = document.querySelector("#orderStatusBadge");
const stepperProgressFill = document.querySelector("#stepperProgressFill");
const stepperSteps = document.querySelector("#stepperSteps");
const carrierTrackingLabel = document.querySelector("#carrierTrackingLabel");
const etaLabel = document.querySelector("#etaLabel");
const orderTotalLabel = document.querySelector("#orderTotalLabel");
const orderItemsList = document.querySelector("#orderItemsList");
const activeResolutionBanner = document.querySelector("#activeResolutionBanner");
const resTitle = document.querySelector("#resTitle");
const resDesc = document.querySelector("#resDesc");
const evidenceGrid = document.querySelector("#evidenceGrid");
const evidenceCount = document.querySelector("#evidenceCount");

// Policy & Team Feed Selectors
const eligibilityPill = document.querySelector("#eligibilityPill");
const returnWindowMetric = document.querySelector("#returnWindowMetric");
const cancellationMetric = document.querySelector("#cancellationMetric");
const policyMessagesList = document.querySelector("#policyMessagesList");
const teamActivityFeed = document.querySelector("#teamActivityFeed");

// Ticket Dialog Selectors
const openTicketBtn = document.querySelector("#openTicketBtn");
const closeTicketBtn = document.querySelector("#closeTicketBtn");
const copyTicketBtn = document.querySelector("#copyTicketBtn");
const ticketModal = document.querySelector("#ticketModal");
const ticketMarkdownView = document.querySelector("#ticketMarkdownView");
const ticketModalTitle = document.querySelector("#ticketModalTitle");

// State & Origins
const DEFAULT_PORT = "4188";
const API_ORIGIN = window.location.protocol === "file:"
  ? `http://127.0.0.1:${DEFAULT_PORT}`
  : window.location.origin;
const WS_ORIGIN = API_ORIGIN.replace(/^http/, "ws");

let liveSocket = null;
let audioContext = null;
let audioStream = null;
let inputSource = null;
let inputProcessor = null;
let cameraStream = null;
let frameTimer = null;
let isRecording = false;
let nextPlaybackTime = 0;
let sessionId = null;
let appState = null;
let allCustomers = [];

// Pre-canned Demo Scenarios for 1-Click Testing
const DEMO_SCENARIOS = [
  {
    id: "out_for_delivery",
    icon: "🚚",
    title: "Check Live Courier ETA (ORD-94301)",
    customerId: "CUST-1001",
    orderNumber: "ORD-94301",
    prompt: "Hi, this is Sarah Jenkins. I'm checking on my coffee order ORD-94301. When is it arriving today and where is the courier right now?",
  },
  {
    id: "return_window",
    icon: "🎧",
    title: "Return Headphones (ORD-88219)",
    customerId: "CUST-1001",
    orderNumber: "ORD-88219",
    prompt: "Hi, I'm Sarah Jenkins. I received my AuraWave headphones on order ORD-88219 three days ago. They don't fit comfortably, so I'd like to initiate a return.",
  },
  {
    id: "damaged_plates",
    icon: "🍽️",
    title: "Damaged Stoneware [Inspect Camera] (ORD-62184)",
    customerId: "CUST-1002",
    orderNumber: "ORD-62184",
    prompt: "Hello, my name is Marcus Vance, order ORD-62184. My ceramic dinnerware set arrived yesterday, but two bowls were shattered in the box. Can I show you on camera?",
  },
  {
    id: "cancel_order",
    icon: "🪑",
    title: "Cancel Desk Chair in Processing (ORD-33018)",
    customerId: "CUST-1003",
    orderNumber: "ORD-33018",
    prompt: "Hi, Elena Rostova here. I placed order ORD-33018 this morning for an ergonomic desk chair, but I need to cancel it before it ships. Can you help me?",
  },
  {
    id: "expired_warranty",
    icon: "🤖",
    title: "Expired Return Window Warranty (ORD-71042)",
    customerId: "CUST-1001",
    orderNumber: "ORD-71042",
    prompt: "Hi, Sarah Jenkins again regarding order ORD-71042. My RoboClean vacuum cleaner stopped charging. I know it's past the 30-day return window, but what are my options?",
  },
  {
    id: "missing_item",
    icon: "🧶",
    title: "Missing Cashmere Sweater (ORD-77621)",
    customerId: "CUST-1005",
    orderNumber: "ORD-77621",
    prompt: "Hi, this is Aisha Patel. I received order ORD-77621 yesterday. The box had the denim and belt, but the cashmere sweater was missing! Can you send a replacement?",
  },
  {
    id: "lost_package",
    icon: "🖥️",
    title: "Marked Delivered But Missing (ORD-44912)",
    customerId: "CUST-1004",
    orderNumber: "ORD-44912",
    prompt: "David Kim here. Order ORD-44912 says my 4K monitor was delivered to my porch two hours ago, but nothing is outside. Can you open a carrier investigation?",
  },
];

// Formatting Utilities
function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setCallStatus(status, tone = "neutral") {
  callStatusText.textContent = status;
  callStatusPill.className = `status-pill ${tone}`.trim();
  if (tone === "speaking" || tone === "live") {
    waveform.classList.add("active");
  } else {
    waveform.classList.remove("active");
  }
}

// REST API Helper
async function api(path, options = {}) {
  const response = await fetch(`${API_ORIGIN}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `HTTP error ${response.status}`);
  }
  return data;
}

// Initialize Application
async function init() {
  renderDemoScenarios();
  setupEventListeners();

  try {
    const health = await api("/api/health");
    systemModelLabel.textContent = `${health.live_model} · Voice: ${health.voice}`;

    const customers = await api("/api/customers");
    allCustomers = customers;
    populateCustomerDropdown(customers);

    const sessionData = await api("/api/sessions", { method: "POST" });
    sessionId = sessionData.session_id;
    applyState(sessionData.state);
    setCallStatus(sessionData.has_api_key ? "Ready" : "API Key Needed", sessionData.has_api_key ? "neutral" : "alert");
  } catch (err) {
    console.error("Initialization error:", err);
    setCallStatus("Backend Error", "alert");
    appendSystemMessage(`Could not connect to backend server: ${err.message}`);
  }
}

// Populate Customer Picker
function populateCustomerDropdown(customers) {
  customerSelect.innerHTML = customers
    .map(
      (c) =>
        `<option value="${c.customer_id}">${escapeHtml(c.full_name)} (${escapeHtml(c.loyalty_tier)})</option>`
    )
    .join("");
}

// Populate Orders Dropdown for Customer
function populateOrderDropdown(orders, selectedOrderNum) {
  if (!orders || !orders.length) {
    orderSelect.innerHTML = "<option value=''>No orders</option>";
    return;
  }
  orderSelect.innerHTML = orders
    .map((o) => {
      const isSel = o.order_number === selectedOrderNum ? "selected" : "";
      return `<option value="${o.order_number}" ${isSel}>${o.order_number} · ${escapeHtml(o.status.toUpperCase())} · $${o.total_amount.toFixed(2)}</option>`;
    })
    .join("");
}

// Render Demo Scenarios Buttons
function renderDemoScenarios() {
  demoScenariosList.innerHTML = DEMO_SCENARIOS.map(
    (s) => `
    <button class="scenario-chip" type="button" data-scenario-id="${s.id}">
      <span>${s.icon}</span>
      <strong>${escapeHtml(s.title)}</strong>
    </button>
  `
  ).join("");
}

// Setup Event Listeners
function setupEventListeners() {
  // Mic Talk Button
  micBtn.addEventListener("click", toggleLiveVoice);

  // Camera Button
  cameraBtn.addEventListener("click", toggleCamera);

  // Reset Session Button
  resetSessionBtn.addEventListener("click", async () => {
    stopLiveVoice();
    stopCamera();
    try {
      const sessionData = await api("/api/sessions", { method: "POST" });
      sessionId = sessionData.session_id;
      applyState(sessionData.state);
      setCallStatus("Session Reset", "neutral");
    } catch (e) {
      appendSystemMessage(e.message);
    }
  });

  // Customer Select Switcher
  customerSelect.addEventListener("change", async (e) => {
    const custId = e.target.value;
    try {
      const state = await api("/api/select_customer", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, customer_id: custId }),
      });
      applyState(state);
      if (liveSocket && liveSocket.readyState === WebSocket.OPEN) {
        liveSocket.send(JSON.stringify({ type: "select_customer", customer_id: custId }));
      }
    } catch (err) {
      console.error(err);
    }
  });

  // Order Select Switcher
  orderSelect.addEventListener("change", async (e) => {
    const orderNum = e.target.value;
    try {
      const state = await api("/api/select_order", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, order_number: orderNum }),
      });
      applyState(state);
      if (liveSocket && liveSocket.readyState === WebSocket.OPEN) {
        liveSocket.send(JSON.stringify({ type: "select_order", order_number: orderNum }));
      }
    } catch (err) {
      console.error(err);
    }
  });

  // Chat Form Text Send
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = "";
    sendCustomerTurn(text);
  });

  // Click on Demo Scenario
  demoScenariosList.addEventListener("click", async (e) => {
    const chip = e.target.closest(".scenario-chip");
    if (!chip) return;
    const sId = chip.dataset.scenarioId;
    const scenario = DEMO_SCENARIOS.find((s) => s.id === sId);
    if (!scenario) return;

    // Switch customer and order first
    customerSelect.value = scenario.customerId;
    try {
      const state = await api("/api/select_customer", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, customer_id: scenario.customerId }),
      });
      applyState(state);

      const ordState = await api("/api/select_order", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, order_number: scenario.orderNumber }),
      });
      applyState(ordState);

      // Auto trigger camera if this scenario inspects camera
      if (sId === "damaged_plates" && !cameraStream) {
        await startCamera();
      }

      // Send the inquiry prompt
      sendCustomerTurn(scenario.prompt);
    } catch (err) {
      console.error(err);
    }
  });

  // CRM Ticket Modal
  openTicketBtn.addEventListener("click", () => {
    ticketMarkdownView.textContent = appState?.ticket_markdown || "No ticket generated yet.";
    ticketModal.showModal();
  });

  closeTicketBtn.addEventListener("click", () => {
    ticketModal.close();
  });

  copyTicketBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(ticketMarkdownView.textContent);
    copyTicketBtn.textContent = "Copied!";
    setTimeout(() => {
      copyTicketBtn.textContent = "Copy Markdown";
    }, 2000);
  });
}

// Connect to Gemini 3.8 Live WebSocket
async function connectLive() {
  if (liveSocket && liveSocket.readyState === WebSocket.OPEN) return;

  setCallStatus("Connecting...", "neutral");
  liveSocket = new WebSocket(`${WS_ORIGIN}/ws/live`);

  liveSocket.onopen = () => {
    setCallStatus("Live Audio Connected", "live");
  };

  liveSocket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleLiveMessage(msg);
    } catch (err) {
      console.error("Error parsing WebSocket message:", err);
    }
  };

  liveSocket.onclose = () => {
    if (isRecording) stopLiveVoice();
    setCallStatus("Ready", "neutral");
  };

  liveSocket.onerror = (err) => {
    console.error("WebSocket error:", err);
    setCallStatus("Connection Error", "alert");
  };

  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("WebSocket timeout")), 8000);
    liveSocket.addEventListener("open", () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
    liveSocket.addEventListener("error", () => {
      clearTimeout(timer);
      reject(new Error("WebSocket connection failed"));
    }, { once: true });
  });
}

// Process Messages from Server
function handleLiveMessage(msg) {
  if (msg.type === "session") {
    sessionId = msg.session_id;
    systemModelLabel.textContent = `${msg.model} · Voice: ${msg.voice}`;
    applyState(msg.state);
  } else if (msg.type === "state") {
    applyState(msg.state);
  } else if (msg.type === "transcript") {
    upsertTurn(msg.speaker || "Agent", msg.text, msg.final);
  } else if (msg.type === "audio") {
    setCallStatus("Agent Speaking", "speaking");
    playPcm24(msg.data);
  } else if (msg.type === "tool") {
    handleToolEvent(msg);
  } else if (msg.type === "interrupted") {
    nextPlaybackTime = audioContext?.currentTime || 0;
    setCallStatus("Live Audio", "live");
  } else if (msg.type === "error") {
    appendSystemMessage(msg.message);
    setCallStatus("Error", "alert");
  }
}

// Handle Incoming Tool Event
function handleToolEvent(entry) {
  const existingIndex = (appState?.tool_activity || []).findIndex((t) => t.id === entry.id);
  const updated = [...(appState?.tool_activity || [])];
  if (existingIndex >= 0) {
    updated[existingIndex] = entry;
  } else {
    updated.push(entry);
  }
  applyState({ ...appState, tool_activity: updated });
}

// Send Customer Turn
async function sendCustomerTurn(text) {
  try {
    await connectLive();
  } catch (err) {
    appendSystemMessage(`Connection error: ${err.message}`);
    return;
  }

  upsertTurn("Customer", text, true);
  setCallStatus("Agent Processing...", "speaking");
  liveSocket.send(JSON.stringify({ type: "text", text }));
}

// Toggle Live Voice Capture
async function toggleLiveVoice() {
  if (isRecording) {
    stopLiveVoice();
  } else {
    await startLiveVoice();
  }
}

// Start Live Microphone Stream (16kHz PCM mono)
async function startLiveVoice() {
  try {
    await connectLive();
    audioStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    audioContext = audioContext || new (window.AudioContext || window.webkitAudioContext)();
    await audioContext.resume();

    inputSource = audioContext.createMediaStreamSource(audioStream);
    inputProcessor = audioContext.createScriptProcessor(4096, 1, 1);

    inputProcessor.onaudioprocess = (e) => {
      if (!isRecording || !liveSocket || liveSocket.readyState !== WebSocket.OPEN) return;
      const inputBuffer = e.inputBuffer.getChannelData(0);
      // Resample browser sample rate (usually 44.1k or 48k) to 16000 Hz PCM16
      const pcm16 = resampleToPcm16(inputBuffer, audioContext.sampleRate, 16000);
      const b64 = arrayBufferToBase64(pcm16.buffer);
      liveSocket.send(JSON.stringify({ type: "audio", data: b64 }));
    };

    inputSource.connect(inputProcessor);
    inputProcessor.connect(audioContext.destination);

    isRecording = true;
    micBtn.classList.add("active");
    micBtnLabel.textContent = "Listening... (Tap to Mute)";
    setCallStatus("Live Listening", "live");
  } catch (err) {
    console.error("Microphone access error:", err);
    appendSystemMessage(`Microphone access error: ${err.message}`);
  }
}

// Stop Live Voice
function stopLiveVoice() {
  isRecording = false;
  micBtn.classList.remove("active");
  micBtnLabel.textContent = "Talk to Assistant";
  if (inputProcessor && inputSource) {
    inputSource.disconnect();
    inputProcessor.disconnect();
  }
  if (audioStream) {
    audioStream.getTracks().forEach((t) => t.stop());
    audioStream = null;
  }
  setCallStatus("Ready", "neutral");
}

// Toggle Camera
async function toggleCamera() {
  if (cameraStream) {
    stopCamera();
  } else {
    await startCamera();
  }
}

// Start Camera Stream & Frame Dispatch (1 Frame / sec)
async function startCamera() {
  try {
    await connectLive();
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
    });
    cameraVideo.srcObject = cameraStream;
    cameraStage.hidden = false;
    cameraBtn.classList.add("active");
    cameraBtn.querySelector(".tool-text").textContent = "Hide Camera";

    // Frame capture interval at 1 frame per 1000ms
    const ctx = captureCanvas.getContext("2d");
    frameTimer = setInterval(() => {
      if (!cameraStream || !liveSocket || liveSocket.readyState !== WebSocket.OPEN) return;
      ctx.drawImage(cameraVideo, 0, 0, captureCanvas.width, captureCanvas.height);
      const dataUrl = captureCanvas.toDataURL("image/jpeg", 0.7);
      const b64 = dataUrl.split(",")[1];
      liveSocket.send(JSON.stringify({ type: "frame", data: b64 }));
    }, 1000);
  } catch (err) {
    console.error("Camera access error:", err);
    appendSystemMessage(`Camera access error: ${err.message}`);
  }
}

// Stop Camera
function stopCamera() {
  if (frameTimer) clearInterval(frameTimer);
  if (cameraStream) {
    cameraStream.getTracks().forEach((t) => t.stop());
    cameraStream = null;
  }
  cameraStage.hidden = true;
  cameraBtn.classList.remove("active");
  cameraBtn.querySelector(".tool-text").textContent = "Show Camera";
}

// Resample audio from browser rate to 16kHz PCM16
function resampleToPcm16(audioBuffer, fromSampleRate, toSampleRate) {
  const ratio = fromSampleRate / toSampleRate;
  const newLength = Math.round(audioBuffer.length / ratio);
  const result = new Int16Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;

  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < audioBuffer.length; i++) {
      accum += audioBuffer[i];
      count++;
    }
    const sample = count ? accum / count : 0;
    const clamped = Math.max(-1, Math.min(1, sample));
    result[offsetResult] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

// Base64 ArrayBuffer converter
function arrayBufferToBase64(buffer) {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

// Play incoming 24kHz PCM audio from Gemini Live
function playPcm24(base64Data) {
  if (!base64Data) return;
  audioContext = audioContext || new (window.AudioContext || window.webkitAudioContext)();
  if (audioContext.state === "suspended") audioContext.resume();

  const binary = window.atob(base64Data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

  const pcm16 = new Int16Array(bytes.buffer);
  const float32 = new Float32Array(pcm16.length);
  for (let i = 0; i < pcm16.length; i++) float32[i] = pcm16[i] / 32768.0;

  const audioBuf = audioContext.createBuffer(1, float32.length, 24000);
  audioBuf.getChannelData(0).set(float32);

  const source = audioContext.createBufferSource();
  source.buffer = audioBuf;
  source.connect(audioContext.destination);

  const now = audioContext.currentTime;
  const startTime = Math.max(now, nextPlaybackTime);
  source.start(startTime);
  nextPlaybackTime = startTime + audioBuf.duration;

  source.onended = () => {
    if (audioContext.currentTime >= nextPlaybackTime - 0.05) {
      setCallStatus(isRecording ? "Live Listening" : "Ready", isRecording ? "live" : "neutral");
    }
  };
}

// Apply Incoming State to UI
function applyState(newState) {
  if (!newState) return;
  appState = newState;

  renderCustomer(newState.customer);
  renderOrder(newState.active_order);
  renderTranscript(newState.transcript);
  renderEvidence(newState.evidence_photos);
  renderPolicy(newState.eligibility);
  renderTeamActivity(newState.tool_activity);
  renderActions(newState.actions_taken);

  ticketMarkdownView.textContent = newState.ticket_markdown || "No ticket generated yet.";
}

// Render Customer Card
function renderCustomer(c) {
  if (!c) return;
  if (customerSelect.value !== c.customer_id) {
    customerSelect.value = c.customer_id;
  }
  customerName.textContent = c.full_name;
  customerEmail.textContent = c.email;
  customerPhone.textContent = c.phone;
  customerAddress.textContent = c.shipping_address;

  const initials = c.full_name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2);
  customerAvatar.textContent = initials;

  const tier = c.loyalty_tier || "Standard";
  customerLoyalty.textContent = tier;
  customerLoyalty.className = `tier-pill ${
    tier.includes("Gold") ? "tier-gold" : tier.includes("Silver") ? "tier-silver" : "tier-platinum"
  }`;

  if (window._lastRenderedCustomerId !== c.customer_id) {
    window._lastRenderedCustomerId = c.customer_id;
    api(`/api/customers/${c.customer_id}/orders`)
      .then((orders) => {
        populateOrderDropdown(orders, appState?.active_order?.order_number);
      })
      .catch(() => {});
  }
}

// Render Active Order Card
function renderOrder(order) {
  if (!order) return;
  orderSelect.value = order.order_number;

  // Status Badge
  const st = order.status.toLowerCase();
  orderStatusBadge.textContent = order.status.toUpperCase().replace(/_/g, " ");
  orderStatusBadge.className = `badge-status ${
    st === "delivered"
      ? "status-delivered"
      : st.includes("transit") || st.includes("delivery")
      ? "status-transit"
      : st === "processing"
      ? "status-processing"
      : "status-cancelled"
  }`;

  // Meta strip
  carrierTrackingLabel.textContent = `${order.carrier} · ${order.tracking_number}`;
  etaLabel.textContent = order.estimated_delivery || "Pending";
  orderTotalLabel.textContent = `$${order.total_amount.toFixed(2)} (${order.payment_method})`;

  // Stepper milestones
  renderStepper(order.status);

  // Line items
  orderItemsList.innerHTML = (order.items || [])
    .map(
      (item) => `
    <div class="item-row">
      <div class="item-left">
        <span class="item-emoji">${item.image_emoji || "📦"}</span>
        <div>
          <div class="item-name">${escapeHtml(item.name)}</div>
          <span class="item-category">${escapeHtml(item.category)} · Qty: ${item.quantity}</span>
        </div>
      </div>
      <div class="item-right">
        <span class="item-price">$${(item.unit_price * item.quantity).toFixed(2)}</span>
        <span class="item-status-pill">${escapeHtml(item.status_tag || (item.is_returnable ? "Returnable" : "Final Sale"))}</span>
      </div>
    </div>
  `
    )
    .join("");
}

// Render 5-Step Tracking Stepper
function renderStepper(status) {
  const steps = [
    { key: "placed", title: "Placed" },
    { key: "processing", title: "Processing" },
    { key: "in_transit", title: "In Transit" },
    { key: "out_for_delivery", title: "Out for Delivery" },
    { key: "delivered", title: "Delivered" },
  ];

  const st = status.toLowerCase();
  let activeIndex = 0;
  if (st === "processing") activeIndex = 1;
  else if (st === "in_transit" || st === "shipped") activeIndex = 2;
  else if (st === "out_for_delivery") activeIndex = 3;
  else if (st === "delivered" || st === "return_requested") activeIndex = 4;
  else if (st === "cancelled") activeIndex = 0;

  const pct = (activeIndex / (steps.length - 1)) * 100;
  stepperProgressFill.style.width = `${pct}%`;

  stepperSteps.innerHTML = steps
    .map((step, idx) => {
      let stateCls = "";
      let icon = idx + 1;
      if (idx < activeIndex) {
        stateCls = "completed";
        icon = "✓";
      } else if (idx === activeIndex) {
        stateCls = "active";
      }
      return `
      <div class="step-node ${stateCls}">
        <div class="step-circle">${icon}</div>
        <span class="step-title">${step.title}</span>
      </div>
    `;
    })
    .join("");
}

// Render Conversation Transcript
function renderTranscript(turns) {
  if (!turns || !turns.length) return;
  turnCounter.textContent = `${turns.length} turns`;

  // Check if there is an active streaming element
  const last = transcriptFeed.lastElementChild;
  const isStreaming = last && last.dataset.streaming === "true";
  const streamingSpeaker = last?.classList.contains("agent-turn") ? "Agent" : "Customer";
  const streamingText = last?.querySelector("p")?.textContent || "";

  transcriptFeed.innerHTML = turns
    .map((t) => {
      const isAgent = t.speaker === "Agent";
      const cls = isAgent ? "agent-turn" : "customer-turn";
      const speakerLabel = isAgent ? "AI ASSISTANT" : "CUSTOMER";
      return `
      <div class="turn ${cls}">
        <span class="turn-badge">${speakerLabel}</span>
        <p>${escapeHtml(t.text)}</p>
      </div>
    `;
    })
    .join("");

  // Restore streaming bubble if it was actively being streamed and not yet committed in turns
  if (isStreaming && streamingText && !turns.some((t) => t.text === streamingText)) {
    upsertTurn(streamingSpeaker, streamingText, false);
  }

  transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
}

function upsertTurn(speaker, text, final = false) {
  if (!text || !text.trim()) return;
  const isAgent = speaker === "Agent";
  const cls = isAgent ? "agent-turn" : "customer-turn";
  const badge = isAgent ? "AI ASSISTANT" : "CUSTOMER";
  const last = transcriptFeed.lastElementChild;

  if (last && last.classList.contains(cls) && last.dataset.streaming === "true") {
    last.querySelector("p").textContent = text;
    if (final) delete last.dataset.streaming;
  } else {
    const div = document.createElement("div");
    div.className = `turn ${cls}`;
    if (!final) div.dataset.streaming = "true";
    div.innerHTML = `<span class="turn-badge">${badge}</span><p>${escapeHtml(text)}</p>`;
    transcriptFeed.appendChild(div);
  }
  transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
}

function appendSystemMessage(text) {
  const div = document.createElement("div");
  div.className = "turn system-turn";
  div.innerHTML = `<span class="turn-badge">SYSTEM</span><p>${escapeHtml(text)}</p>`;
  transcriptFeed.appendChild(div);
  transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
}

// Render Evidence Photos
function renderEvidence(photos) {
  evidenceCount.textContent = `${photos?.length || 0} Photos`;
  if (!photos || !photos.length) {
    evidenceGrid.innerHTML = `
      <div class="evidence-empty">
        <span class="empty-icon">📷</span>
        <p>No damage photos pinned yet. When customer shows a damaged package or broken item on camera, the AI agent will inspect it, capture evidence, and pin it here.</p>
      </div>
    `;
    return;
  }

  evidenceGrid.innerHTML = photos
    .map(
      (p) => `
    <div class="evidence-card">
      <div class="evidence-img-wrap">
        <img src="${p.data_url || "assets/package_placeholder.png"}" alt="Evidence Frame" />
        <span class="evidence-badge ${p.confirmed ? "confirmed" : "unconfirmed"}">
          ${p.confirmed ? "✓ Damage Confirmed" : "⚠️ Unverified"}
        </span>
      </div>
      <div class="evidence-details">
        <strong class="evidence-obs">${escapeHtml(p.observation)}</strong>
        <span class="evidence-meta">Seen on camera ${escapeHtml(p.captured_at)} · ${escapeHtml(p.item_name || "Item")}</span>
      </div>
    </div>
  `
    )
    .join("");
}

// Render Policy Eligibility
function renderPolicy(el) {
  if (!el) return;

  const isEligible = el.is_within_return_window || el.is_cancellable || el.is_replacement_eligible;
  eligibilityPill.textContent = isEligible ? "ELIGIBLE" : "POLICY REVIEW";
  eligibilityPill.className = `badge-pill ${isEligible ? "pass" : "fail"}`;

  if (el.days_since_delivery != null) {
    const daysLeft = 30 - el.days_since_delivery;
    if (daysLeft >= 0) {
      returnWindowMetric.textContent = `${daysLeft} Days Left`;
      returnWindowMetric.className = "metric-val text-success";
    } else {
      returnWindowMetric.textContent = "Expired (>30d)";
      returnWindowMetric.className = "metric-val text-danger";
    }
  } else {
    returnWindowMetric.textContent = "Pending Delivery";
    returnWindowMetric.className = "metric-val text-muted";
  }

  if (el.is_cancellable) {
    cancellationMetric.textContent = "Open (Processing)";
    cancellationMetric.className = "metric-val text-success";
  } else {
    cancellationMetric.textContent = "Closed";
    cancellationMetric.className = "metric-val text-muted";
  }

  policyMessagesList.innerHTML = (el.validation_messages || [])
    .map((msg) => `<li>${escapeHtml(msg)}</li>`)
    .join("");
}

// Render Team Activity Feed
function renderTeamActivity(activity) {
  if (!activity || !activity.length) {
    teamActivityFeed.innerHTML = `<li class="empty-feed">Background tool executions will stream in real time.</li>`;
    return;
  }

  const items = [...activity].reverse().slice(0, 8);
  teamActivityFeed.innerHTML = items
    .map((t) => {
      const isRunning = t.phase === "running";
      const meta = isRunning
        ? "executing..."
        : t.scheduling === "INTERRUPT"
        ? "INTERRUPT"
        : `${t.duration_ms || 0}ms`;
      return `
      <li class="feed-item">
        <span class="feed-dot ${isRunning ? "running" : "done"}"></span>
        <div class="feed-item-body">
          <span class="feed-tool-name">${escapeHtml(t.name)}</span>
          <span class="feed-headline">${escapeHtml(t.headline || "")}</span>
        </div>
        <span class="feed-meta">${escapeHtml(meta)}</span>
      </li>
    `;
    })
    .join("");
}

// Render Executed Actions Banner
function renderActions(actions) {
  if (!actions || !actions.length) {
    activeResolutionBanner.hidden = true;
    return;
  }

  const latest = actions[actions.length - 1];
  activeResolutionBanner.hidden = false;
  resTitle.textContent = `Action Completed: ${latest.action || "Order Resolution"}`;
  resDesc.textContent = latest.message || latest.instructions || "Resolution executed successfully.";
}

// Start application on page load
window.addEventListener("DOMContentLoaded", init);
