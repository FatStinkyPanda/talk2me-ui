/**
 * Talk2Me UI - Common JavaScript Functionality
 */

// Global state
let currentProgress = 0;
let progressInterval = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];

// DOM ready
document.addEventListener("DOMContentLoaded", function () {
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
      },
    });

    if (response.ok) {
      statusIndicator.className = "status-indicator connected";
      statusText.textContent = "Connected";
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (error) {
    statusIndicator.className = "status-indicator error";
    statusText.textContent = "Disconnected";
    console.warn("Backend status check failed:", error);
  }
}

/**
 * Sidebar Data Management
 */
async function updateSidebarData() {
  try {
    // Update voice count
    const voiceResponse = await fetch("/api/voices");
    if (voiceResponse.ok) {
      const voices = await voiceResponse.json();
      document.getElementById("voice-count").textContent = voices.length;
    }

    // Update project count (placeholder)
    document.getElementById("project-count").textContent = "0";

    // Update storage usage (placeholder)
    document.getElementById("storage-usage").textContent = "0 MB";
  } catch (error) {
    console.warn("Failed to update sidebar data:", error);
  }
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

  if (!action) {
    showError("Form action not specified");
    return;
  }

  // Show progress modal
  showProgressModal("Processing...");

  try {
    const response = await fetch(action, {
      method: form.method || "POST",
      body: formData,
      headers: {
        Accept: "application/json",
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
    for (let file of files) {
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
    showSuccess("Recording started");
  } catch (error) {
    showError("Failed to start recording: " + error.message);
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    isRecording = false;
    updateRecordingUI(false);
    showSuccess("Recording stopped");
  }
}

function updateRecordingUI(recording) {
  const recordButton = document.getElementById("record-button");
  const recordStatus = document.getElementById("record-status");

  if (!recordButton || !recordStatus) return;

  if (recording) {
    recordButton.classList.add("recording");
    recordButton.classList.remove("stopped");
    recordButton.innerHTML = "<span>⏹️</span><span>Stop</span>";
    recordStatus.textContent = "Recording...";
  } else {
    recordButton.classList.remove("recording");
    recordButton.classList.add("stopped");
    recordButton.innerHTML = "<span>🎤</span><span>Record</span>";
    recordStatus.textContent = "Click to start recording";
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
  const waveform = playerElement.querySelector(".audio-waveform");
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

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
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
