/**
 * Talk2Me UI - Common JavaScript Functionality
 */

// Global state
let currentProgress = 0;
let progressInterval = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];

// Touch interaction state
let touchStartX = 0;
let touchStartY = 0;
let touchStartTime = 0;

// CSRF token management
function getCsrfToken() {
  const tokenMeta = document.querySelector('meta[name="csrf-token"]');
  return tokenMeta ? tokenMeta.getAttribute("content") : null;
}

function getCsrfHeaders() {
  const token = getCsrfToken();
  if (token) {
    return { "X-CSRF-Token": token };
  }
  return {};
}

// Initialize i18next
async function initializeI18n() {
  await i18next
    .use(i18nextBrowserLanguageDetector)
    .use(i18nextHttpBackend)
    .init({
      fallbackLng: "en",
      debug: false,
      backend: {
        loadPath: "/static/locales/{{lng}}/common.json",
      },
      detection: {
        order: ["localStorage", "navigator", "htmlTag"],
        caches: ["localStorage"],
      },
      interpolation: {
        escapeValue: false, // React already escapes values
      },
    });

  // Update page language
  document.documentElement.lang = i18next.language;

  // Update language selector
  updateLanguageSelector();
}

// Language change function
function changeLanguage(lang) {
  i18next.changeLanguage(lang).then(() => {
    document.documentElement.lang = lang;
    updateLanguageSelector();
    // Optionally reload the page to get server-side translations
    // location.reload();
  });
}

// Update language selector to match current language
function updateLanguageSelector() {
  const selector = document.getElementById("language-select");
  if (selector) {
    selector.value = i18next.language;
  }
}

// DOM ready
document.addEventListener("DOMContentLoaded", async function () {
  await initializeI18n();
  initializeApp();
});

function initializeApp() {
  // Initialize backend status check
  checkBackendStatus();
  setInterval(checkBackendStatus, 30000); // Check every 30 seconds

  // Initialize sidebar data
  updateSidebarData();

  // Initialize form handlers
  initializeForms();

  // Initialize file upload handlers
  initializeFileUploads();

  // Initialize recording interface if present
  initializeRecording();

  // Initialize audio players
  initializeAudioPlayers();

  // Initialize touch interactions
  initializeTouchInteractions();

  // Initialize PWA features
  initializePWA();
}

/**
 * Touch Interaction Management
 */
function initializeTouchInteractions() {
  // Add touch feedback to interactive elements
  document
    .querySelectorAll(
      ".btn, .conversation-button, .record-button, .file-upload, .play-btn",
    )
    .forEach((element) => {
      addTouchFeedback(element);
    });

  // Add swipe gestures for modals
  document.querySelectorAll(".modal-content").forEach((modal) => {
    addSwipeToClose(modal);
  });

  // Prevent zoom on double-tap for iOS
  let lastTouchEnd = 0;
  document.addEventListener(
    "touchend",
    (event) => {
      const now = Date.now();
      if (now - lastTouchEnd <= 300) {
        event.preventDefault();
      }
      lastTouchEnd = now;
    },
    false,
  );

  // Prevent context menu on long press
  document.addEventListener("contextmenu", (event) => {
    if (event.target.closest(".btn, .conversation-button, .record-button")) {
      event.preventDefault();
    }
  });
}

function addTouchFeedback(element) {
  let touchStartTime = 0;
  let hasMoved = false;

  element.addEventListener(
    "touchstart",
    (event) => {
      touchStartTime = Date.now();
      hasMoved = false;
      element.classList.add("touch-active");

      // Prevent scrolling when touching buttons
      if (
        element.classList.contains("btn") ||
        element.classList.contains("conversation-button") ||
        element.classList.contains("record-button")
      ) {
        event.preventDefault();
      }
    },
    { passive: false },
  );

  element.addEventListener("touchmove", () => {
    hasMoved = true;
    element.classList.remove("touch-active");
  });

  element.addEventListener("touchend", (event) => {
    element.classList.remove("touch-active");

    // Handle long press for additional actions
    const touchDuration = Date.now() - touchStartTime;
    if (touchDuration > 500 && !hasMoved) {
      handleLongPress(element, event);
    }
  });

  // Add mouse feedback for desktop testing
  element.addEventListener("mousedown", () => {
    element.classList.add("touch-active");
  });

  element.addEventListener("mouseup", () => {
    element.classList.remove("touch-active");
  });

  element.addEventListener("mouseleave", () => {
    element.classList.remove("touch-active");
  });
}

function addSwipeToClose(modal) {
  let startX = 0;
  let startY = 0;
  let isTracking = false;

  modal.addEventListener(
    "touchstart",
    (event) => {
      startX = event.touches[0].clientX;
      startY = event.touches[0].clientY;
      isTracking = true;
    },
    { passive: true },
  );

  modal.addEventListener(
    "touchmove",
    (event) => {
      if (!isTracking) return;

      const currentX = event.touches[0].clientX;
      const currentY = event.touches[0].clientY;
      const diffX = currentX - startX;
      const diffY = currentY - startY;

      // Only handle vertical swipes (down to close)
      if (Math.abs(diffY) > Math.abs(diffX) && diffY > 50) {
        modal.style.transform = `translateY(${diffY}px)`;
        modal.style.opacity = Math.max(0, 1 - Math.abs(diffY) / 200);
      }
    },
    { passive: true },
  );

  modal.addEventListener(
    "touchend",
    (event) => {
      if (!isTracking) return;

      const currentY = event.changedTouches[0].clientY;
      const diffY = currentY - startY;

      isTracking = false;

      // Close modal if swiped down enough
      if (diffY > 100) {
        const modalElement = modal.closest(".modal");
        if (modalElement) {
          modalElement.classList.remove("show");
        }
      }

      // Reset transform
      modal.style.transform = "";
      modal.style.opacity = "";
    },
    { passive: true },
  );
}

function handleLongPress(element, event) {
  // Add haptic feedback if available
  if (navigator.vibrate) {
    navigator.vibrate(50);
  }

  // Show additional options for long press (future enhancement)
  if (element.classList.contains("conversation-button")) {
    showQuickActions(element, event);
  }
}

function showQuickActions(button, event) {
  // Create quick action menu for conversation buttons
  const actions = ["Start Conversation", "View History", "Settings"];
  const menu = document.createElement("div");
  menu.className = "quick-actions-menu";
  menu.style.cssText = `
    position: absolute;
    background: white;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 1000;
    padding: 8px 0;
    min-width: 150px;
  `;

  actions.forEach((action) => {
    const item = document.createElement("div");
    item.textContent = action;
    item.style.cssText = `
      padding: 12px 16px;
      cursor: pointer;
      font-size: 14px;
      color: #374151;
    `;
    item.addEventListener("click", () => {
      console.log("Quick action:", action);
      document.body.removeChild(menu);
    });
    item.addEventListener("mouseenter", () => {
      item.style.backgroundColor = "#f3f4f6";
    });
    item.addEventListener("mouseleave", () => {
      item.style.backgroundColor = "";
    });
    menu.appendChild(item);
  });

  document.body.appendChild(menu);

  // Position menu
  const rect = button.getBoundingClientRect();
  menu.style.left = rect.left + "px";
  menu.style.top = rect.bottom + 8 + "px";

  // Remove menu when clicking elsewhere
  const removeMenu = (e) => {
    if (!menu.contains(e.target)) {
      document.body.removeChild(menu);
      document.removeEventListener("click", removeMenu);
    }
  };
  setTimeout(() => document.addEventListener("click", removeMenu), 100);
}

/**
 * PWA Management
 */
function initializePWA() {
  // Register service worker
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker
        .register("/static/service-worker.js")
        .then((registration) => {
          console.log("SW registered: ", registration);
        })
        .catch((registrationError) => {
          console.log("SW registration failed: ", registrationError);
        });
    });
  }

  // Handle PWA install prompt
  let deferredPrompt;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    showInstallPrompt();
  });

  // Handle successful installation
  window.addEventListener("appinstalled", () => {
    console.log("PWA was installed");
    hideInstallPrompt();
  });

  // Handle online/offline status
  window.addEventListener("online", () => {
    hideOfflineIndicator();
    showSuccess("Back online");
    checkBackendStatus();
  });

  window.addEventListener("offline", () => {
    showOfflineIndicator();
    showError("You are offline. Some features may not be available.");
  });

  // Show offline indicator if already offline
  if (!navigator.onLine) {
    showOfflineIndicator();
  }
}

function showInstallPrompt() {
  const installButton = document.createElement("button");
  installButton.className = "btn btn-primary install-prompt";
  installButton.innerHTML = "<span>📱</span><span>Install App</span>";
  installButton.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 1000;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  `;

  installButton.addEventListener("click", () => {
    hideInstallPrompt();
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === "accepted") {
          console.log("User accepted the install prompt");
        }
        deferredPrompt = null;
      });
    }
  });

  document.body.appendChild(installButton);

  // Auto-hide after 10 seconds
  setTimeout(() => hideInstallPrompt(), 10000);
}

function hideInstallPrompt() {
  const prompt = document.querySelector(".install-prompt");
  if (prompt) {
    prompt.remove();
  }
}

function showOfflineIndicator() {
  hideOfflineIndicator(); // Remove existing
  const indicator = document.createElement("div");
  indicator.className = "offline-indicator";
  indicator.innerHTML = "<span>⚠️</span><span>Offline Mode</span>";
  document.body.appendChild(indicator);
}

function hideOfflineIndicator() {
  const indicator = document.querySelector(".offline-indicator");
  if (indicator) {
    indicator.remove();
  }
}

/**
 * Backend Status Management
 */
async function checkBackendStatus() {
  const statusIndicator = document.getElementById("status-indicator");
  const statusText = document.getElementById("status-text");

  if (!statusIndicator || !statusText) return;

  try {
    const response = await fetch("/api/health", {
      method: "GET",
      headers: {
        Accept: "application/json",
        ...getCsrfHeaders(),
      },
    });

    if (response.ok) {
      statusIndicator.className = "status-indicator connected";
      statusText.textContent = i18next.t("status.connected");
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch {
    statusIndicator.className = "status-indicator error";
    statusText.textContent = i18next.t("status.disconnected");
  }
}

/**
 * Sidebar Data Management
 */
async function updateSidebarData() {
  // Update voice count
  const voiceResponse = await fetch("/api/voices");
  if (voiceResponse.ok) {
    const data = await voiceResponse.json();
    document.getElementById("voice-count").textContent = (
      data.voices || []
    ).length;
  }

  // Update project count (placeholder)
  document.getElementById("project-count").textContent = "0";

  // Update storage usage (placeholder)
  document.getElementById("storage-usage").textContent = "0 MB";
}

/**
 * Form Management
 */
function initializeForms() {
  // Add form validation and submission handling
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", handleFormSubmit);
  });

  // Add input validation
  document.querySelectorAll("input, textarea, select").forEach((input) => {
    input.addEventListener("blur", validateInput);
    input.addEventListener("input", clearValidationError);
  });
}

async function handleFormSubmit(event) {
  event.preventDefault();

  const form = event.target;
  const formData = new FormData(form);
  const action = form.getAttribute("data-action") || form.action;
  const method = form.getAttribute("data-method") || form.method || "POST";

  if (!action) {
    showError("Form action not specified");
    return;
  }

  // Handle voice forms specially
  if (form.id === "create-voice-form" || form.id === "edit-voice-form") {
    return handleVoiceFormSubmit(form, formData, action, method);
  }

  // Check if form has files
  const hasFiles = Array.from(formData.values()).some(
    (value) => value instanceof File,
  );

  if (hasFiles) {
    return handleFileUploadForm(form, formData, action, method);
  }

  // Show progress modal
  showProgressModal("Processing...");

  try {
    const response = await fetch(action, {
      method: method,
      body: formData,
      headers: {
        Accept: "application/json",
        ...getCsrfHeaders(),
      },
    });

    const result = await response.json();

    if (response.ok) {
      showSuccess(result.message || "Operation completed successfully");
      form.reset();

      // Refresh sidebar data
      updateSidebarData();

      // Refresh page content if needed
      if (form.getAttribute("data-refresh") === "true") {
        setTimeout(() => location.reload(), 1500);
      }
    } else {
      throw new Error(result.detail || result.message || "Operation failed");
    }
  } catch (error) {
    showError(error.message || "An error occurred");
  } finally {
    closeProgressModal();
  }
}

function validateInput(event) {
  const input = event.target;
  const value = input.value.trim();
  const isRequired = input.hasAttribute("required");
  const minLength = input.getAttribute("minlength");
  const pattern = input.getAttribute("pattern");

  let isValid = true;
  let errorMessage = "";

  if (isRequired && !value) {
    isValid = false;
    errorMessage = "This field is required";
  } else if (minLength && value.length < parseInt(minLength)) {
    isValid = false;
    errorMessage = `Minimum length is ${minLength} characters`;
  } else if (pattern && !new RegExp(pattern).test(value)) {
    isValid = false;
    errorMessage = "Invalid format";
  }

  if (!isValid) {
    showInputError(input, errorMessage);
  } else {
    clearInputError(input);
  }

  return isValid;
}

function showInputError(input, message) {
  clearInputError(input);

  input.classList.add("error");
  const errorElement = document.createElement("div");
  errorElement.className = "input-error";
  errorElement.textContent = message;
  input.parentNode.appendChild(errorElement);
}

function clearInputError(input) {
  input.classList.remove("error");
  const errorElement = input.parentNode.querySelector(".input-error");
  if (errorElement) {
    errorElement.remove();
  }
}

function clearValidationError(event) {
  const input = event.target;
  if (input.classList.contains("error")) {
    clearInputError(input);
  }
}

async function handleVoiceFormSubmit(form, formData, action, method) {
  // Validate voice samples
  const sampleFiles = formData.getAll("samples");
  if (sampleFiles.length > 0) {
    const validation = await validateVoiceSamples(sampleFiles);
    if (!validation.valid) {
      showError(validation.message);
      return;
    }
  }

  // For edit, append voice ID to action
  if (form.id === "edit-voice-form") {
    const voiceId = formData.get("id");
    if (voiceId) {
      action = `${action}/${voiceId}`;
    }
  }

  // Handle file upload with progress
  return handleFileUploadForm(form, formData, action, method);
}

async function handleFileUploadForm(form, formData, action, method) {
  showProgressModal("Uploading files...");

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        const percentComplete = (event.loaded / event.total) * 100;
        updateProgress(
          percentComplete,
          `Uploading... ${Math.round(percentComplete)}%`,
        );
      }
    });

    xhr.addEventListener("load", () => {
      closeProgressModal();

      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const result = JSON.parse(xhr.responseText);
          showSuccess(result.message || "Operation completed successfully");
          form.reset();

          // Clear file lists
          const fileLists = form.querySelectorAll(".sample-files-list");
          fileLists.forEach((list) => (list.innerHTML = ""));

          // Refresh sidebar data
          updateSidebarData();

          // Refresh page content if needed
          if (form.getAttribute("data-refresh") === "true") {
            setTimeout(() => location.reload(), 1500);
          }

          // Close modals if any
          if (form.id === "edit-voice-form") {
            closeEditModal();
          }

          resolve();
        } catch (error) {
          showError("Invalid response from server");
          reject(error);
        }
      } else {
        try {
          const result = JSON.parse(xhr.responseText);
          showError(result.detail || result.message || "Operation failed");
        } catch {
          showError("Operation failed");
        }
        reject(new Error("Request failed"));
      }
    });

    xhr.addEventListener("error", () => {
      closeProgressModal();
      showError("Network error occurred");
      reject(new Error("Network error"));
    });

    xhr.open(method, action);
    xhr.setRequestHeader("Accept", "application/json");

    // Add CSRF token header
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      xhr.setRequestHeader("X-CSRF-Token", csrfToken);
    }

    xhr.send(formData);
  });
}

async function validateVoiceSamples(files) {
  if (files.length === 0) return { valid: true };

  // Check count
  if (files.length < 3 || files.length > 10) {
    return {
      valid: false,
      message: "Please upload between 3 and 10 voice samples",
    };
  }

  // Check file types
  for (const file of files) {
    if (
      !file.name.toLowerCase().endsWith(".wav") &&
      !file.type.includes("audio/wav")
    ) {
      return { valid: false, message: "All files must be WAV format" };
    }

    // Check file size (rough check, WAV files are typically small)
    if (file.size > 50 * 1024 * 1024) {
      // 50MB max
      return {
        valid: false,
        message: "File size too large. Maximum 50MB per file",
      };
    }
  }

  // Check durations
  for (const file of files) {
    try {
      const duration = await getAudioDuration(file);
      if (duration < 5 || duration > 30) {
        return {
          valid: false,
          message: `Audio duration must be between 5-30 seconds. File "${file.name}" is ${duration.toFixed(1)} seconds`,
        };
      }
    } catch {
      return {
        valid: false,
        message: `Could not validate audio file "${file.name}". Please ensure it's a valid WAV file`,
      };
    }
  }

  return { valid: true };
}

function getAudioDuration(file) {
  return new Promise((resolve, reject) => {
    const audio = new Audio();
    const url = URL.createObjectURL(file);

    audio.addEventListener("loadedmetadata", () => {
      URL.revokeObjectURL(url);
      resolve(audio.duration);
    });

    audio.addEventListener("error", () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not load audio"));
    });

    audio.src = url;
  });
}

/**
 * File Upload Management
 */
function initializeFileUploads() {
  document.querySelectorAll(".file-upload").forEach((uploadArea) => {
    const input = uploadArea.querySelector(".file-input");
    const text = uploadArea.querySelector(".file-upload-text");

    if (!input || !text) return;

    // Click to open file dialog
    uploadArea.addEventListener("click", () => input.click());

    // Drag and drop
    uploadArea.addEventListener("dragover", handleDragOver);
    uploadArea.addEventListener("dragleave", handleDragLeave);
    uploadArea.addEventListener("drop", handleFileDrop);

    // File selection
    input.addEventListener("change", (event) => {
      handleFileSelection(event.target.files, text);
    });
  });
}

function handleDragOver(event) {
  event.preventDefault();
  event.currentTarget.classList.add("dragover");
}

function handleDragLeave(event) {
  event.preventDefault();
  event.currentTarget.classList.remove("dragover");
}

function handleFileDrop(event) {
  event.preventDefault();
  event.currentTarget.classList.remove("dragover");

  const files = event.dataTransfer.files;
  const text = event.currentTarget.querySelector(".file-upload-text");
  const input = event.currentTarget.querySelector(".file-input");

  if (input && files.length > 0) {
    // Update input files
    const dt = new DataTransfer();
    for (const file of files) {
      dt.items.add(file);
    }
    input.files = dt.files;

    handleFileSelection(files, text);
  }
}

function handleFileSelection(files, textElement) {
  if (files.length === 0) {
    textElement.textContent = "Choose files or drag them here";
    return;
  }

  if (files.length === 1) {
    textElement.textContent = files[0].name;
  } else {
    textElement.textContent = `${files.length} files selected`;
  }
}

/**
 * Recording Interface
 */
function initializeRecording() {
  const recordButton = document.getElementById("record-button");
  const recordStatus = document.getElementById("record-status");

  if (!recordButton || !recordStatus) return;

  recordButton.addEventListener("click", toggleRecording);
}

async function toggleRecording() {
  const recordButton = document.getElementById("record-button");
  const recordStatus = document.getElementById("record-status");

  if (!recordButton || !recordStatus) return;

  if (isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = (event) => {
      audioChunks.push(event.data);
    };

    mediaRecorder.onstop = () => {
      const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
      handleRecordingComplete(audioBlob);
      stream.getTracks().forEach((track) => track.stop());
    };

    mediaRecorder.start();
    isRecording = true;

    updateRecordingUI(true);
    showSuccess(i18next.t("recording.recordingStarted"));
  } catch (error) {
    showError("Failed to start recording: " + error.message);
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    isRecording = false;
    updateRecordingUI(false);
    showSuccess(i18next.t("recording.recordingStopped"));
  }
}

function updateRecordingUI(recording) {
  const recordButton = document.getElementById("record-button");
  const recordStatus = document.getElementById("record-status");

  if (!recordButton || !recordStatus) return;

  if (recording) {
    recordButton.classList.add("recording");
    recordButton.classList.remove("stopped");
    recordButton.innerHTML = `<span>⏹️</span><span>${i18next.t("recording.stopRecording")}</span>`;
    recordStatus.textContent = i18next.t("recording.recordingStarted");
  } else {
    recordButton.classList.remove("recording");
    recordButton.classList.add("stopped");
    recordButton.innerHTML = `<span>🎤</span><span>${i18next.t("recording.startRecording")}</span>`;
    recordStatus.textContent = i18next.t("recording.clickToStartRecording");
  }
}

function handleRecordingComplete(audioBlob) {
  // Create download link or upload to server
  const url = URL.createObjectURL(audioBlob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `recording_${Date.now()}.wav`;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Audio Player Management
 */
function initializeAudioPlayers() {
  document.querySelectorAll(".audio-player").forEach((player) => {
    initializeAudioPlayer(player);
  });
}

function initializeAudioPlayer(playerElement) {
  const playBtn = playerElement.querySelector(".play-btn");
  const duration = playerElement.querySelector(".audio-duration");
  const audio = playerElement.querySelector("audio");

  if (!playBtn || !audio) return;

  playBtn.addEventListener("click", () => {
    if (audio.paused) {
      audio.play();
      playBtn.innerHTML = "⏸️";
    } else {
      audio.pause();
      playBtn.innerHTML = "▶️";
    }
  });

  audio.addEventListener("ended", () => {
    playBtn.innerHTML = "▶️";
  });

  audio.addEventListener("timeupdate", () => {
    if (duration && audio.duration) {
      const current = formatTime(audio.currentTime);
      const total = formatTime(audio.duration);
      duration.textContent = `${current} / ${total}`;
    }
  });
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

/**
 * Progress Modal Management
 */
function showProgressModal(title = "Processing...", initialProgress = 0) {
  const modal = document.getElementById("progress-modal");
  const titleElement = document.getElementById("progress-title");
  const fillElement = document.getElementById("progress-fill");
  const textElement = document.getElementById("progress-text");

  if (!modal || !titleElement || !fillElement || !textElement) return;

  titleElement.textContent = title;
  currentProgress = initialProgress;
  updateProgress(initialProgress, "Initializing...");

  modal.classList.add("show");

  // Start progress animation
  if (progressInterval) clearInterval(progressInterval);
  progressInterval = setInterval(() => {
    if (currentProgress < 90) {
      currentProgress += Math.random() * 10;
      updateProgress(currentProgress, "Processing...");
    }
  }, 500);
}

function updateProgress(progress, text) {
  const fillElement = document.getElementById("progress-fill");
  const textElement = document.getElementById("progress-text");

  if (fillElement) {
    fillElement.style.width = Math.min(progress, 100) + "%";
  }

  if (textElement) {
    textElement.textContent = text;
  }
}

function closeProgressModal() {
  const modal = document.getElementById("progress-modal");

  if (modal) {
    modal.classList.remove("show");
  }

  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }

  currentProgress = 0;
}

/**
 * Error Modal Management
 */
function showError(message, details = "") {
  const modal = document.getElementById("error-modal");
  const messageElement = document.getElementById("error-message");
  const detailsElement = document.getElementById("error-details");

  if (!modal || !messageElement) return;

  messageElement.textContent = message;
  if (detailsElement) {
    detailsElement.textContent = details;
  }

  modal.classList.add("show");

  // Update modal title
  const titleElement = modal.querySelector("h3");
  if (titleElement) {
    titleElement.textContent = i18next.t("modals.error");
  }
}

function closeErrorModal() {
  const modal = document.getElementById("error-modal");
  if (modal) {
    modal.classList.remove("show");
  }
}

/**
 * Success Modal Management
 */
function showSuccess(message) {
  const modal = document.getElementById("success-modal");
  const messageElement = document.getElementById("success-message");

  if (!modal || !messageElement) return;

  messageElement.textContent = message;
  modal.classList.add("show");

  // Update modal title
  const titleElement = modal.querySelector("h3");
  if (titleElement) {
    titleElement.textContent = i18next.t("modals.success");
  }

  // Auto-close after 3 seconds
  setTimeout(() => {
    closeSuccessModal();
  }, 3000);
}

function closeSuccessModal() {
  const modal = document.getElementById("success-modal");
  if (modal) {
    modal.classList.remove("show");
  }
}

/**
 * Utility Functions
 */
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

function throttle(func, limit) {
  let inThrottle;
  return function () {
    const args = arguments;
    const context = this;
    if (!inThrottle) {
      func.apply(context, args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

function formatFileSize(bytes) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function closeEditModal() {
  const modal = document.getElementById("edit-voice-modal");
  if (modal) {
    modal.classList.remove("show");
  }
  const form = document.getElementById("edit-voice-form");
  if (form) {
    form.reset();
  }
}

// Export functions for global use
window.Talk2MeUI = {
  showProgressModal,
  closeProgressModal,
  showError,
  closeErrorModal,
  showSuccess,
  closeSuccessModal,
  updateProgress,
  formatFileSize,
  debounce,
  throttle,
};
