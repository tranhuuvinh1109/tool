/**
 * YouTube Transcript Sync - Frontend Application Engine
 * Synchronizes YouTube IFrame Player with interactive transcript segments & Gemini 2.5 Flash AI.
 */

// Application State
let player = null;
let isPlayerReady = false;
let currentVideoId = null;
let transcriptData = [];
let activeSegmentIndex = -1;
let syncInterval = null;
let isAutoScrollEnabled = true;
let showVietnamese = true;
let isUserScrolling = false;
let userScrollTimeout = null;

// DOM Elements
const youtubeUrlInput = document.getElementById("youtube-url");
const btnLoad = document.getElementById("btn-load");
const loadingOverlay = document.getElementById("loading-overlay");
const loadingMessage = document.getElementById("loading-message");
const errorAlert = document.getElementById("error-alert");
const errorTitle = document.getElementById("error-title");
const errorDesc = document.getElementById("error-desc");
const btnCloseError = document.getElementById("btn-close-error");
const playerPlaceholder = document.getElementById("player-placeholder");

const videoTitleEl = document.getElementById("video-title");
const badgeLanguage = document.getElementById("badge-language");
const badgeSegments = document.getElementById("badge-segments");
const badgeDuration = document.getElementById("badge-duration");

const transcriptList = document.getElementById("transcript-list");
const transcriptSearch = document.getElementById("transcript-search");
const btnClearSearch = document.getElementById("btn-clear-search");
const transcriptCount = document.getElementById("transcript-count");
const toggleAutoScroll = document.getElementById("toggle-autoscroll");
const toggleVietnamese = document.getElementById("toggle-vietnamese");

const btnExportTxt = document.getElementById("btn-export-txt");
const btnExportSrt = document.getElementById("btn-export-srt");

// AI Workspace Elements
const btnGenerateSummary = document.getElementById("btn-generate-summary");
const resultSummary = document.getElementById("result-summary");
const chatQuestionInput = document.getElementById("chat-question");
const btnSendChat = document.getElementById("btn-send-chat");
const resultChat = document.getElementById("result-chat");
const explainInput = document.getElementById("explain-input");
const btnRunExplain = document.getElementById("btn-run-explain");
const resultExplain = document.getElementById("result-explain");
const btnGenerateFlashcards = document.getElementById("btn-generate-flashcards");
const resultFlashcards = document.getElementById("result-flashcards");

// Global YouTube IFrame API Callback
function onYouTubeIframeAPIReady() {
    console.log("YouTube IFrame API loaded and ready.");
}

// Initialize Event Listeners
document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    setupPresetButtons();
    setupAITabs();
    setupFontSizePicker();
});

function setupEventListeners() {
    btnLoad.addEventListener("click", handleLoadTranscript);
    
    youtubeUrlInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") handleLoadTranscript();
    });

    btnCloseError.addEventListener("click", () => {
        errorAlert.classList.add("hidden");
    });

    toggleAutoScroll.addEventListener("change", (e) => {
        isAutoScrollEnabled = e.target.checked;
    });

    if (toggleVietnamese) {
        toggleVietnamese.addEventListener("change", (e) => {
            showVietnamese = e.target.checked;
            document.querySelectorAll(".segment-text-vi").forEach((el) => {
                if (showVietnamese) {
                    el.classList.remove("hidden-vi");
                } else {
                    el.classList.add("hidden-vi");
                }
            });
        });
    }

    // Detect user manual scroll on transcript list
    transcriptList.addEventListener("scroll", () => {
        if (!isUserScrolling) {
            isUserScrolling = true;
        }
        clearTimeout(userScrollTimeout);
        userScrollTimeout = setTimeout(() => {
            isUserScrolling = false;
        }, 4000); // resume auto-scroll after 4s idle
    });

    // Search filter
    transcriptSearch.addEventListener("input", handleSearchFilter);
    btnClearSearch.addEventListener("click", () => {
        transcriptSearch.value = "";
        btnClearSearch.classList.add("hidden");
        handleSearchFilter();
    });

    // Export buttons
    btnExportTxt.addEventListener("click", exportAsTXT);
    btnExportSrt.addEventListener("click", exportAsSRT);

    // AI Feature Actions
    btnGenerateSummary.addEventListener("click", handleGenerateSummary);
    btnSendChat.addEventListener("click", handleSendChat);
    chatQuestionInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") handleSendChat();
    });
    btnRunExplain.addEventListener("click", handleRunExplain);
    btnGenerateFlashcards.addEventListener("click", handleGenerateFlashcards);
}

function setupPresetButtons() {
    document.querySelectorAll(".preset-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const url = btn.getAttribute("data-url");
            youtubeUrlInput.value = url;
            handleLoadTranscript();
        });
    });
}

function setupAITabs() {
    const tabBtns = document.querySelectorAll(".ai-tab-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");

    tabBtns.forEach((btn) => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");

            tabBtns.forEach((b) => b.classList.remove("active"));
            tabPanes.forEach((p) => p.classList.remove("active"));

            btn.classList.add("active");
            const activePane = document.getElementById(targetTab);
            if (activePane) activePane.classList.add("active");
        });
    });
}

function setupFontSizePicker() {
    const fontBtns = document.querySelectorAll(".btn-font");
    fontBtns.forEach((btn) => {
        btn.addEventListener("click", () => {
            fontBtns.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            const size = btn.getAttribute("data-size");
            let fontSize = "1rem";
            if (size === "sm") fontSize = "0.88rem";
            if (size === "lg") fontSize = "1.15rem";
            document.documentElement.style.setProperty("--transcript-size", fontSize);
        });
    });
}

// Handle Transcript Loading from API
async function handleLoadTranscript() {
    const url = youtubeUrlInput.value.trim();
    if (!url) {
        showError("Missing URL", "Please enter a valid YouTube video URL.");
        return;
    }

    showLoading("Extracting subtitles, merging sentences & translating into Vietnamese...");
    hideError();

    try {
        const response = await fetch(`/api/transcript?url=${encodeURIComponent(url)}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load transcript.");
        }

        currentVideoId = data.video_id;
        transcriptData = data.segments || [];

        // Update Meta UI
        videoTitleEl.innerText = data.title || `YouTube Video (${currentVideoId})`;
        badgeLanguage.innerHTML = `<i class="fa-solid fa-language"></i> Lang: ${data.language.toUpperCase()}`;
        badgeSegments.innerHTML = `<i class="fa-solid fa-list-ol"></i> Sentences: ${transcriptData.length}`;
        
        const lastSegment = transcriptData[transcriptData.length - 1];
        const totalDurationSec = lastSegment ? lastSegment.end : 0;
        badgeDuration.innerHTML = `<i class="fa-regular fa-clock"></i> ${formatTime(totalDurationSec)}`;

        // Initialize Player & Render Transcript
        initYouTubePlayer(currentVideoId);
        renderTranscript(transcriptData);
        startSyncLoop();

        hideLoading();
        updateStatus("Synced", "green");
    } catch (err) {
        hideLoading();
        showError("Transcript Error", err.message);
        updateStatus("Error", "amber");
    }
}

// Initialize YouTube IFrame Player
function initYouTubePlayer(videoId) {
    if (playerPlaceholder) playerPlaceholder.style.display = "none";

    if (player && typeof player.loadVideoById === "function") {
        player.loadVideoById(videoId);
    } else {
        player = new YT.Player("player", {
            videoId: videoId,
            playerVars: {
                autoplay: 1,
                modestbranding: 1,
                rel: 0
            },
            events: {
                onReady: () => {
                    isPlayerReady = true;
                },
                onStateChange: (event) => {
                    if (event.data === YT.PlayerState.PLAYING) {
                        startSyncLoop();
                    }
                }
            }
        });
    }
}

// Render Transcript Segment Cards with Bilingual Display
function renderTranscript(segments) {
    transcriptList.innerHTML = "";

    if (!segments || segments.length === 0) {
        transcriptList.innerHTML = `
            <div class="empty-transcript-state">
                <i class="fa-regular fa-comment-dots empty-icon"></i>
                <h3>No Transcript Lines Available</h3>
            </div>`;
        transcriptCount.innerText = "0 / 0";
        return;
    }

    transcriptCount.innerText = `${segments.length} / ${segments.length}`;
    const viClass = showVietnamese ? "" : "hidden-vi";

    const fragment = document.createDocumentFragment();

    segments.forEach((seg) => {
        const segDiv = document.createElement("div");
        segDiv.className = "transcript-segment";
        segDiv.id = `segment-${seg.id}`;
        segDiv.setAttribute("data-id", seg.id);
        segDiv.setAttribute("data-start", seg.start);
        segDiv.setAttribute("data-end", seg.end);

        const viHtml = seg.text_vi ? `<div class="segment-text-vi ${viClass}"><i class="fa-solid fa-language"></i> <span>${escapeHtml(seg.text_vi)}</span></div>` : "";

        segDiv.innerHTML = `
            <div class="segment-time">
                <span class="timestamp">${formatTime(seg.start)}</span>
            </div>
            <div class="segment-text">
                <div class="segment-text-original">${escapeHtml(seg.text)}</div>
                ${viHtml}
            </div>
            <div class="segment-actions">
                <button class="btn-explain-mini" title="Explain with Gemini AI" onclick="explainSegmentText(event, ${seg.id})">
                    <i class="fa-solid fa-sparkles"></i> Explain
                </button>
            </div>
        `;

        // Click segment to seek video
        segDiv.addEventListener("click", (e) => {
            if (e.target.closest(".btn-explain-mini")) return;
            if (player && typeof player.seekTo === "function") {
                player.seekTo(seg.start, true);
                if (player.getPlayerState() !== YT.PlayerState.PLAYING) {
                    player.playVideo();
                }
            }
        });

        fragment.appendChild(segDiv);
    });

    transcriptList.appendChild(fragment);
}

// Binary Search Algorithm for O(log N) Segment Detection
function findActiveSegmentIndex(currentTime, segments) {
    if (!segments || segments.length === 0) return -1;
    let low = 0;
    let high = segments.length - 1;

    while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        const seg = segments[mid];

        if (currentTime >= seg.start && currentTime < seg.end) {
            return mid;
        } else if (currentTime < seg.start) {
            high = mid - 1;
        } else {
            low = mid + 1;
        }
    }

    if (currentTime >= segments[segments.length - 1].end) {
        return segments.length - 1;
    }
    return -1;
}

// Time Synchronization Loop
function startSyncLoop() {
    if (syncInterval) clearInterval(syncInterval);

    syncInterval = setInterval(() => {
        if (!player || typeof player.getCurrentTime !== "function") return;
        
        const currentTime = player.getCurrentTime();
        const newIndex = findActiveSegmentIndex(currentTime, transcriptData);

        if (newIndex !== activeSegmentIndex && newIndex >= 0) {
            // Remove previous active state
            if (activeSegmentIndex >= 0) {
                const prevEl = document.getElementById(`segment-${activeSegmentIndex}`);
                if (prevEl) prevEl.classList.remove("active");
            }

            activeSegmentIndex = newIndex;

            // Highlight new active segment
            const activeEl = document.getElementById(`segment-${activeSegmentIndex}`);
            if (activeEl) {
                activeEl.classList.add("active");

                // Auto-scroll if enabled and user isn't manually scrolling
                if (isAutoScrollEnabled && !isUserScrolling) {
                    activeEl.scrollIntoView({
                        behavior: "smooth",
                        block: "center"
                    });
                }
            }
        }
    }, 200);
}

// Search Filter Handling (English + Vietnamese)
function handleSearchFilter() {
    const query = transcriptSearch.value.trim().toLowerCase();
    
    if (query.length > 0) {
        btnClearSearch.classList.remove("hidden");
    } else {
        btnClearSearch.classList.add("hidden");
    }

    const segmentEls = transcriptList.querySelectorAll(".transcript-segment");
    let matchCount = 0;

    segmentEls.forEach((el) => {
        const id = parseInt(el.getAttribute("data-id"));
        const segmentObj = transcriptData[id];
        if (!segmentObj) return;

        const origText = segmentObj.text || "";
        const viText = segmentObj.text_vi || "";
        
        const matchOrig = origText.toLowerCase().includes(query);
        const matchVi = viText.toLowerCase().includes(query);

        if (!query || matchOrig || matchVi) {
            el.style.display = "flex";
            matchCount++;

            const origEl = el.querySelector(".segment-text-original");
            const viSpan = el.querySelector(".segment-text-vi span");

            if (query) {
                const regex = new RegExp(`(${escapeRegExp(query)})`, "gi");
                if (origEl) origEl.innerHTML = escapeHtml(origText).replace(regex, '<mark class="search-match">$1</mark>');
                if (viSpan) viSpan.innerHTML = escapeHtml(viText).replace(regex, '<mark class="search-match">$1</mark>');
            } else {
                if (origEl) origEl.innerHTML = escapeHtml(origText);
                if (viSpan) viSpan.innerHTML = escapeHtml(viText);
            }
        } else {
            el.style.display = "none";
        }
    });

    transcriptCount.innerText = `${matchCount} / ${transcriptData.length}`;
}

// Gemini AI Integration Functions
async function handleGenerateSummary() {
    if (!transcriptData || transcriptData.length === 0) {
        resultSummary.innerText = "Please load a video transcript first.";
        return;
    }

    resultSummary.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Generating summary with Gemini 2.5 Flash...`;
    const fullText = transcriptData.map((s) => s.text).join(" ");

    try {
        const res = await fetch("/api/ai/summarize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ video_id: currentVideoId, transcript: fullText })
        });
        const data = await res.json();
        resultSummary.innerText = data.summary || "No summary response received.";
    } catch (err) {
        resultSummary.innerText = "Error: " + err.message;
    }
}

async function handleSendChat() {
    const question = chatQuestionInput.value.trim();
    if (!question) return;
    if (!transcriptData || transcriptData.length === 0) {
        resultChat.innerText = "Please load a video transcript first.";
        return;
    }

    resultChat.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Analyzing video content for answer...`;
    const fullText = transcriptData.map((s) => s.text).join(" ");

    try {
        const res = await fetch("/api/ai/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ transcript: fullText, question: question })
        });
        const data = await res.json();
        resultChat.innerText = data.answer || "No response received.";
    } catch (err) {
        resultChat.innerText = "Error: " + err.message;
    }
}

function explainSegmentText(event, segmentId) {
    event.stopPropagation();
    const seg = transcriptData[segmentId];
    if (!seg) return;

    const explainTabBtn = document.querySelector('.ai-tab-btn[data-tab="tab-explain"]');
    if (explainTabBtn) explainTabBtn.click();

    explainInput.value = seg.text;
    
    const prevSeg = transcriptData[segmentId - 1] ? transcriptData[segmentId - 1].text : "";
    const nextSeg = transcriptData[segmentId + 1] ? transcriptData[segmentId + 1].text : "";
    const context = `${prevSeg} [TARGET] ${seg.text} [/TARGET] ${nextSeg}`;

    runExplainRequest(seg.text, context);
}

async function handleRunExplain() {
    const text = explainInput.value.trim();
    if (!text) return;
    runExplainRequest(text, "");
}

async function runExplainRequest(segmentText, context) {
    resultExplain.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Generating explanation with Gemini 2.5 Flash...`;

    try {
        const res = await fetch("/api/ai/explain", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ segment_text: segmentText, context: context })
        });
        const data = await res.json();
        resultExplain.innerText = data.explanation || "No explanation returned.";
    } catch (err) {
        resultExplain.innerText = "Error: " + err.message;
    }
}

async function handleGenerateFlashcards() {
    if (!transcriptData || transcriptData.length === 0) {
        resultFlashcards.innerHTML = `<p class="placeholder-text">Please load a video transcript first.</p>`;
        return;
    }

    resultFlashcards.innerHTML = `<p class="placeholder-text"><i class="fa-solid fa-spinner fa-spin"></i> Extracting flashcards...</p>`;
    const fullText = transcriptData.map((s) => s.text).join(" ");

    try {
        const res = await fetch("/api/ai/flashcards", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ transcript: fullText })
        });
        const data = await res.json();

        const cards = data.flashcards || [];
        if (cards.length === 0) {
            resultFlashcards.innerHTML = `<p class="placeholder-text">No flashcards were generated.</p>`;
            return;
        }

        resultFlashcards.innerHTML = cards.map((card) => `
            <div class="flashcard-item">
                <div class="flashcard-term">${escapeHtml(card.term)}</div>
                <div class="flashcard-def">${escapeHtml(card.definition)}</div>
            </div>
        `).join("");
    } catch (err) {
        resultFlashcards.innerHTML = `<p class="placeholder-text">Error: ${escapeHtml(err.message)}</p>`;
    }
}

// Export Transcript Utilities
function exportAsTXT() {
    if (!transcriptData || transcriptData.length === 0) return;

    const lines = transcriptData.map((s) => {
        let line = `[${formatTime(s.start)}] ${s.text}`;
        if (s.text_vi) line += `\n   (VI) ${s.text_vi}`;
        return line;
    });
    const content = lines.join("\n\n");
    downloadFile(`transcript_${currentVideoId || "export"}.txt`, content, "text/plain");
}

function exportAsSRT() {
    if (!transcriptData || transcriptData.length === 0) return;

    let srt = "";
    transcriptData.forEach((s, idx) => {
        srt += `${idx + 1}\n`;
        srt += `${formatSrtTime(s.start)} --> ${formatSrtTime(s.end)}\n`;
        srt += `${s.text}\n`;
        if (s.text_vi) srt += `${s.text_vi}\n`;
        srt += `\n`;
    });

    downloadFile(`transcript_${currentVideoId || "export"}.srt`, srt, "text/plain");
}

function downloadFile(filename, text, mimeType) {
    const blob = new Blob([text], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Formatters & Helper Utilities
function formatTime(seconds) {
    const secNum = Math.floor(seconds);
    const hours = Math.floor(secNum / 3600);
    const minutes = Math.floor((secNum % 3600) / 60);
    const secs = secNum % 60;

    const pad = (n) => (n < 10 ? "0" + n : n);

    if (hours > 0) {
        return `${pad(hours)}:${pad(minutes)}:${pad(secs)}`;
    }
    return `${pad(minutes)}:${pad(secs)}`;
}

function formatSrtTime(seconds) {
    const secNum = Math.floor(seconds);
    const ms = Math.floor((seconds - secNum) * 1000);
    const hours = Math.floor(secNum / 3600);
    const minutes = Math.floor((secNum % 3600) / 60);
    const secs = secNum % 60;

    const pad = (n, len = 2) => String(n).padStart(len, "0");

    return `${pad(hours)}:${pad(minutes)}:${pad(secs)},${pad(ms, 3)}`;
}

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function showLoading(msg) {
    loadingMessage.innerText = msg || "Loading...";
    loadingOverlay.classList.remove("hidden");
}

function hideLoading() {
    loadingOverlay.classList.add("hidden");
}

function showError(title, desc) {
    errorTitle.innerText = title;
    errorDesc.innerText = desc;
    errorAlert.classList.remove("hidden");
}

function hideError() {
    errorAlert.classList.add("hidden");
}

function updateStatus(text, color) {
    const statusText = document.getElementById("status-text");
    const statusDot = document.querySelector(".status-dot");
    if (statusText) statusText.innerText = text;
    if (statusDot) {
        statusDot.className = `status-dot ${color}`;
    }
}
