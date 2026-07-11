// State management
let jobId = null;
let cropper = null;
let logoData = null;
let videoWidth = 0;
let videoHeight = 0;
let videoDuration = 0;
let statusInterval = null;

const logoOptions = {
  position: "bottom-right",
  scale: 20,
  opacity: 100,
  margin: 10,
};

// DOM Elements
const uploadView = document.getElementById("upload-view");
const workspaceView = document.getElementById("workspace-view");
const processingView = document.getElementById("processing-view");
const resultView = document.getElementById("result-view");

const dropZone = document.getElementById("drop-zone");
const videoInput = document.getElementById("video-input");
const uploadProgressContainer = document.getElementById(
  "upload-progress-container",
);
const uploadProgressBar = document.getElementById("upload-progress-bar");
const uploadPercentage = document.getElementById("upload-percentage");
const uploadFilename = document.getElementById("upload-filename");
const uploadLabel = document.getElementById("upload-status");

const previewImage = document.getElementById("preview-image");
const cropStats = document.getElementById("crop-stats");
const metaResolution = document.getElementById("meta-resolution");
const metaDuration = document.getElementById("meta-duration");
const metaFPS = document.getElementById("meta-fps");

const logoInput = document.getElementById("logo-input");
const logoPreviewBox = document.getElementById("logo-preview-box");
const logoPreviewPlaceholder = document.getElementById(
  "logo-preview-placeholder",
);
const logoPreviewImg = document.getElementById("logo-preview-img");
const btnRemoveLogo = document.getElementById("btn-remove-logo");
const logoSettingsPanel = document.getElementById("logo-settings-panel");

const logoScale = document.getElementById("logo-scale");
const scaleBadge = document.getElementById("scale-badge");
const logoOpacity = document.getElementById("logo-opacity");
const opacityBadge = document.getElementById("opacity-badge");
const logoMargin = document.getElementById("logo-margin");
const marginBadge = document.getElementById("margin-badge");

const btnGenerate = document.getElementById("btn-generate");
const btnAbortWorkspace = document.getElementById("btn-abort-workspace");

const processBar = document.getElementById("process-bar");
const processPercent = document.getElementById("process-percent");
const processEta = document.getElementById("process-eta");

const outputVideoRender = document.getElementById("output-video-render");
const btnDownload = document.getElementById("btn-download");
const btnReset = document.getElementById("btn-reset");

// Splitting Panel DOM Elements
const enableSplit = document.getElementById("enable-split");
const splitSettingsPanel = document.getElementById("split-settings-panel");
const splitCount = document.getElementById("split-count");
const splitBadge = document.getElementById("split-badge");
const splitHint = document.getElementById("split-hint");

// --- UPLOAD HANDLER ---

// Drag and drop events
["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(
    eventName,
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add("dragover");
    },
    false,
  );
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(
    eventName,
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("dragover");
    },
    false,
  );
});

dropZone.addEventListener("drop", (e) => {
  const dt = e.dataTransfer;
  const files = dt.files;
  if (files.length > 0) {
    handleVideoFile(files[0]);
  }
});

videoInput.addEventListener("change", (e) => {
  if (videoInput.files.length > 0) {
    handleVideoFile(videoInput.files[0]);
  }
});

function handleVideoFile(file) {
  const allowedExtensions = /(\.mp4|\.mov|\.avi)$/i;
  if (!allowedExtensions.exec(file.name)) {
    alert("Unsupported file format. Please upload an MP4, MOV, or AVI video.");
    return;
  }

  // Toggle progress UI
  uploadProgressContainer.classList.remove("d-none");
  uploadFilename.innerHTML = `<i class="bi bi-file-earmark-play me-2"></i>${file.name}`;
  uploadProgressBar.style.width = "0%";
  uploadPercentage.textContent = "0%";
  uploadLabel.textContent = "Uploading file...";

  const formData = new FormData();
  formData.append("video", file);

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/upload", true);

  xhr.upload.addEventListener("progress", (e) => {
    if (e.lengthComputable) {
      const percentComplete = Math.round((e.loaded / e.total) * 100);
      uploadProgressBar.style.width = percentComplete + "%";
      uploadPercentage.textContent = percentComplete + "%";
      if (percentComplete === 100) {
        uploadLabel.textContent = "Analyzing and extracting preview...";
      }
    }
  });

  xhr.onload = function () {
    if (xhr.status === 200) {
      try {
        const response = JSON.parse(xhr.responseText);
        setupWorkspace(response);
      } catch (e) {
        alert("Failed to parse upload reply details.");
        resetUploadView();
      }
    } else {
      try {
        const response = JSON.parse(xhr.responseText);
        alert("Upload failed: " + (response.error || "Server error"));
      } catch (err) {
        alert("Upload failed with status code: " + xhr.status);
      }
      resetUploadView();
    }
  };

  xhr.onerror = function () {
    alert("A network error occurred during upload.");
    resetUploadView();
  };

  xhr.send(formData);
}

function resetUploadView() {
  uploadProgressContainer.classList.add("d-none");
  uploadProgressBar.style.width = "0%";
  uploadPercentage.textContent = "0%";
  videoInput.value = "";
}

// --- WORKSPACE CONFIGURATIONS ---

function setupWorkspace(data) {
  jobId = data.job_id;
  videoWidth = data.width;
  videoHeight = data.height;

  // Badges update
  metaResolution.textContent = `${data.width} × ${data.height}`;
  metaDuration.textContent = `${data.duration}s`;
  metaFPS.textContent = `${data.fps} FPS`;
  videoDuration = data.duration;

  // Setting images to crop view
  previewImage.src = data.first_frame;

  // Switch views
  uploadView.classList.add("d-none");
  workspaceView.classList.remove("d-none");

  // Initialize CropperJS on loaded image
  if (cropper) {
    cropper.destroy();
  }

  setTimeout(() => {
    cropper = new Cropper(previewImage, {
      viewMode: 1,
      dragMode: "move",
      autoCropArea: 0.8,
      restore: false,
      guides: true,
      center: true,
      highlight: false,
      cropBoxMovable: true,
      cropBoxResizable: true,
      toggleDragModeOnDblclick: false,
      crop(event) {
        const cropData = cropper.getData(true);
        cropStats.textContent = `X: ${cropData.x}, Y: ${cropData.y}, W: ${cropData.width}, H: ${cropData.height}`;
      },
    });
  }, 100);

  // Set initial split hint values
  updateSplitHint();
}

// --- LOGO UPLOADS & CONFIG ---

logoInput.addEventListener("change", (e) => {
  if (logoInput.files.length > 0) {
    const file = logoInput.files[0];
    if (file.type !== "image/png") {
      alert("Please select a transparent PNG formatted file.");
      return;
    }

    const reader = new FileReader();
    reader.onload = function (evt) {
      logoData = evt.target.result;

      // Show preview thumbnail
      logoPreviewPlaceholder.style.display = "none";
      logoPreviewImg.src = logoData;
      logoPreviewImg.style.display = "block";
      btnRemoveLogo.classList.remove("d-none");

      // Activate adjustment sliders panel
      logoSettingsPanel.classList.remove("opacity-50", "pointer-events-none");
    };
    reader.readAsDataURL(file);
  }
});

btnRemoveLogo.addEventListener("click", () => {
  logoData = null;
  logoInput.value = "";
  logoPreviewImg.style.display = "none";
  logoPreviewImg.src = "";
  logoPreviewPlaceholder.style.display = "block";
  btnRemoveLogo.classList.add("d-none");

  // Mute adjustment sliders panel
  logoSettingsPanel.classList.add("opacity-50", "pointer-events-none");
});

// Setting ranges updates
logoScale.addEventListener("input", () => {
  logoOptions.scale = parseInt(logoScale.value);
  scaleBadge.textContent = logoOptions.scale + "%";
});

logoOpacity.addEventListener("input", () => {
  logoOptions.opacity = parseInt(logoOpacity.value);
  opacityBadge.textContent = logoOptions.opacity + "%";
});

logoMargin.addEventListener("input", () => {
  logoOptions.margin = parseInt(logoMargin.value);
  marginBadge.textContent = logoOptions.margin + " px";
});

// Helper for position query
document.addEventListener("change", (e) => {
  if (e.target && e.target.name === "logo-position") {
    logoOptions.position = e.target.value;
  }
});

// Event listeners for video splitting settings
enableSplit.addEventListener("change", () => {
  if (enableSplit.checked) {
    splitSettingsPanel.classList.remove("opacity-50", "pointer-events-none");
  } else {
    splitSettingsPanel.classList.add("opacity-50", "pointer-events-none");
  }
  updateSplitHint();
});

splitCount.addEventListener("input", () => {
  const value = splitCount.value;
  splitBadge.textContent = value + " parts";
  updateSplitHint();
});

function updateSplitHint() {
  if (!videoDuration) return;
  const count = parseInt(splitCount.value);
  const partDuration = (videoDuration / count).toFixed(2);
  splitHint.textContent = `Video will be split equally into ${count} parts (approx. ${partDuration}s per part).`;
}

// --- PROCESSING TRIGGER ---

btnGenerate.addEventListener("click", () => {
  if (!jobId || !cropper) return;

  btnGenerate.disabled = true;

  const isSplitEnabled = enableSplit.checked;
  const splitVal = isSplitEnabled ? parseInt(splitCount.value) : 1;

  const cropData = cropper.getData(true);
  const payload = {
    job_id: jobId,
    crop: {
      x: cropData.x,
      y: cropData.y,
      width: cropData.width,
      height: cropData.height,
    },
    logo: logoData, // null or Base64 string
    logo_options: logoOptions,
    split_count: splitVal,
  };

  fetch("/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.error) {
        alert("Processing error: " + data.error);
        btnGenerate.disabled = false;
      } else {
        showProcessingView();
      }
    })
    .catch((err) => {
      alert("Failed to connect to process endpoint.");
      btnGenerate.disabled = false;
    });
});

function showProcessingView() {
  workspaceView.classList.add("d-none");
  processingView.classList.remove("d-none");

  processBar.style.width = "0%";
  processPercent.textContent = "0%";
  processEta.textContent = "estimating...";

  // Set polling status interval
  statusInterval = setInterval(pollJobStatus, 1000);
}

function pollJobStatus() {
  if (!jobId) return;

  fetch(`/status?job_id=${jobId}`)
    .then((res) => res.json())
    .then((data) => {
      if (data.error) {
        clearInterval(statusInterval);
        alert("Status retrieval fault: " + data.error);
        btnGenerate.disabled = false;
        processingView.classList.add("d-none");
        workspaceView.classList.remove("d-none");
        return;
      }

      if (data.status === "processing" || data.status === "uploaded") {
        const pct = data.progress || 0;
        processBar.style.width = pct + "%";
        processPercent.textContent = pct + "%";

        if (data.eta && data.eta > 0) {
          processEta.textContent = `${data.eta} seconds`;
        } else {
          processEta.textContent = "estimating...";
        }
      } else if (data.status === "completed") {
        clearInterval(statusInterval);
        showResultView();
      } else if (data.status === "failed") {
        clearInterval(statusInterval);
        alert(
          "FFmpeg processing failed!\n\nDetails:\n" +
            (data.error || "Unknown rendering exception. Check inputs."),
        );
        btnGenerate.disabled = false;
        processingView.classList.add("d-none");
        workspaceView.classList.remove("d-none");
      }
    })
    .catch((err) => {
      console.warn("Network issue encountered while polling status:", err);
    });
}

// --- RESULT VIEW ---

function showResultView() {
  processingView.classList.add("d-none");
  resultView.classList.remove("d-none");

  // Force refresh cache for previewing video
  const randStr = new Date().getTime();
  outputVideoRender.src = `/download?t=${randStr}`;
  outputVideoRender.load();

  btnDownload.href = "/download";

  const isSplitEnabled = enableSplit.checked;
  const resultMessage = document.querySelector("#result-view p.text-secondary");

  if (isSplitEnabled) {
    if (resultMessage) {
      resultMessage.innerHTML =
        "Your video has been cropped and split successfully! Preview shows the first segment. Click <strong>Download Video</strong> to fetch all parts in a single ZIP.";
    }
    btnDownload.innerHTML =
      '<i class="bi bi-file-earmark-zip-fill me-2"></i>Download ZIP Archive';
  } else {
    if (resultMessage) {
      resultMessage.textContent =
        "Your cropped video is ready for preview and high-quality download.";
    }
    btnDownload.innerHTML =
      '<i class="bi bi-cloud-arrow-down-fill me-2"></i>Download Video';
  }
}

// --- RESET AND ABORT CONTROLLERS ---

btnReset.addEventListener("click", () => {
  location.reload();
});

btnAbortWorkspace.addEventListener("click", () => {
  if (
    confirm(
      "Are you sure you want to discard current selection and upload another file?",
    )
  ) {
    location.reload();
  }
});
