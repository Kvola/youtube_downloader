/** @odoo-module **/
/**
 * YouTube Downloader — Lecteur Vidéo Professionnel
 * Composant OWL avancé : raccourcis clavier, auto-masquage des contrôles,
 * PiP, double-clic plein écran, localStorage, barre de buffer, preview temps
 */

import { Component, onMounted, onPatched, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ─── Constantes ──────────────────────────────────────────────────────────────
const LS_VOLUME_KEY = "yt_player_volume";
const LS_RATE_KEY = "yt_player_rate";
const LS_MUTED_KEY = "yt_player_muted";
const CONTROLS_HIDE_DELAY = 3000; // ms
const SKIP_SECONDS = 10;
const VOLUME_STEP = 0.05;

export class YoutubeVideoPlayer extends Component {
    static template = "youtube_downloader.VideoPlayerDialog";
    static props = {
        close: { type: Function },
        recordId: { type: Number },
        recordName: { type: String, optional: true },
        isAudio: { type: Boolean, optional: true },
        streamUrl: { type: String, optional: true },
        thumbnailUrl: { type: String, optional: true },
        videoDuration: { type: String, optional: true },
        videoAuthor: { type: String, optional: true },
        fileSize: { type: String, optional: true },
        quality: { type: String, optional: true },
        // Playlist props
        onTrackEnded: { type: Function, optional: true },
        onNextTrack: { type: Function, optional: true },
        onPrevTrack: { type: Function, optional: true },
        hasNext: { type: Boolean, optional: true },
        hasPrev: { type: Boolean, optional: true },
        isPlaylist: { type: Boolean, optional: true },
        autoPlay: { type: Boolean, optional: true },
    };
    static defaultProps = {
        recordName: "Vidéo",
        isAudio: false,
        streamUrl: "",
        thumbnailUrl: "",
        videoDuration: "",
        videoAuthor: "",
        fileSize: "",
        quality: "",
        onTrackEnded: null,
        onNextTrack: null,
        onPrevTrack: null,
        hasNext: false,
        hasPrev: false,
        isPlaylist: false,
        autoPlay: false,
    };

    setup() {
        this.notification = useService("notification");
        this.mediaRef = useRef("mediaPlayer");
        this.progressRef = useRef("progressBar");
        this.containerRef = useRef("playerContainer");

        // Charger les préférences depuis localStorage
        const storedVolume = localStorage.getItem(LS_VOLUME_KEY);
        const savedVolume = storedVolume !== null ? parseFloat(storedVolume) : 1;
        const storedRate = localStorage.getItem(LS_RATE_KEY);
        const savedRate = storedRate !== null ? parseFloat(storedRate) : 1;
        const savedMuted = localStorage.getItem(LS_MUTED_KEY) === "true";

        this.state = useState({
            isPlaying: false,
            currentTime: "00:00",
            totalTime: "00:00",
            rawCurrentTime: 0,
            rawDuration: 0,
            progress: 0,
            buffered: 0,
            volume: savedVolume,
            isMuted: savedMuted,
            isFullscreen: false,
            isLoading: true,
            hasError: false,
            errorMessage: "",
            playbackRate: savedRate,
            showControls: true,
            hoverTime: "",
            hoverPosition: 0,
            showHoverTime: false,
            isPiP: false,
            showSpeedMenu: false,
        });

        this.streamUrl = this.props.streamUrl || `/youtube_downloader/stream/${this.props.recordId}`;
        this._controlsTimer = null;
        this._keyHandler = null;
        this._fullscreenHandler = null;
        this._hasAutoPlayed = false;

        onMounted(() => this._initPlayer());
        onWillUnmount(() => this._destroy());
    }

    get playbackRates() {
        return [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3];
    }

    get volumeIcon() {
        if (this.state.isMuted || this.state.volume === 0) return "fa-volume-off";
        if (this.state.volume < 0.33) return "fa-volume-down";
        return "fa-volume-up";
    }

    get pipSupported() {
        return "pictureInPictureEnabled" in document && !this.props.isAudio;
    }

    // ─── Initialisation ─────────────────────────────────────────────────

    _initPlayer() {
        this._setupMediaEvents();
        this._setupKeyboardShortcuts();
        this._setupFullscreenListener();
        this._setupDoubleClick();
        this._setupClickOutside();
        this._resetControlsTimer();
    }

    _setupMediaEvents() {
        const media = this.mediaRef.el;
        if (!media) return;

        // Appliquer les préférences sauvegardées
        media.volume = this.state.volume;
        media.muted = this.state.isMuted;
        media.playbackRate = this.state.playbackRate;

        media.addEventListener("loadedmetadata", () => {
            this.state.totalTime = this._formatTime(media.duration);
            this.state.rawDuration = media.duration;
            this.state.isLoading = false;
        });

        media.addEventListener("timeupdate", () => {
            this.state.currentTime = this._formatTime(media.currentTime);
            this.state.rawCurrentTime = media.currentTime;
            this.state.progress = (media.currentTime / media.duration) * 100 || 0;
        });

        media.addEventListener("progress", () => {
            if (media.buffered.length > 0) {
                const end = media.buffered.end(media.buffered.length - 1);
                this.state.buffered = (end / media.duration) * 100 || 0;
            }
        });

        media.addEventListener("play", () => { this.state.isPlaying = true; });
        media.addEventListener("pause", () => { this.state.isPlaying = false; });
        media.addEventListener("ended", () => {
            this.state.isPlaying = false;
            this.state.progress = 100;
            // Notify playlist for auto-advance
            if (this.props.onTrackEnded) {
                this.props.onTrackEnded();
            }
        });
        media.addEventListener("waiting", () => { this.state.isLoading = true; });
        media.addEventListener("canplay", () => {
            this.state.isLoading = false;
            // Auto-play si demandé (lecture continue en playlist)
            if (this.props.autoPlay && !this._hasAutoPlayed) {
                this._hasAutoPlayed = true;
                media.play().catch(() => {});
            }
        });

        media.addEventListener("error", () => {
            this.state.hasError = true;
            this.state.isLoading = false;
            const errCode = media.error?.code;
            const messages = {
                1: "Lecture interrompue",
                2: "Erreur réseau — vérifiez votre connexion",
                3: "Erreur de décodage — format non supporté",
                4: "Format non supporté par le navigateur",
            };
            this.state.errorMessage = messages[errCode] || "Erreur de lecture inconnue";
        });

        media.addEventListener("volumechange", () => {
            this.state.volume = media.volume;
            this.state.isMuted = media.muted;
        });

        // PiP events
        media.addEventListener("enterpictureinpicture", () => { this.state.isPiP = true; });
        media.addEventListener("leavepictureinpicture", () => { this.state.isPiP = false; });

        // Safety: if metadata is already loaded (cached), update state immediately
        if (media.readyState >= 1) {
            this.state.totalTime = this._formatTime(media.duration);
            this.state.rawDuration = media.duration;
            this.state.isLoading = false;
        }
        // Safety: if media can already play
        if (media.readyState >= 4) {
            this.state.isLoading = false;
        }
    }

    _setupKeyboardShortcuts() {
        this._keyHandler = (e) => {
            // Ne pas interférer avec les inputs
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

            const media = this.mediaRef.el;
            if (!media) return;

            switch (e.key) {
                case " ":
                case "k":
                    e.preventDefault();
                    this.togglePlay();
                    break;
                case "ArrowLeft":
                case "j":
                    e.preventDefault();
                    this.skipBackward();
                    this._showSkipFeedback("backward");
                    break;
                case "ArrowRight":
                case "l":
                    e.preventDefault();
                    this.skipForward();
                    this._showSkipFeedback("forward");
                    break;
                case "ArrowUp":
                    e.preventDefault();
                    this._adjustVolume(VOLUME_STEP);
                    break;
                case "ArrowDown":
                    e.preventDefault();
                    this._adjustVolume(-VOLUME_STEP);
                    break;
                case "m":
                    e.preventDefault();
                    this.toggleMute();
                    break;
                case "f":
                    e.preventDefault();
                    this.toggleFullscreen();
                    break;
                case "p":
                    if (e.shiftKey) {
                        e.preventDefault();
                        this.togglePiP();
                    } else if (this.props.isPlaylist && this.props.hasPrev && this.props.onPrevTrack) {
                        e.preventDefault();
                        this.props.onPrevTrack();
                    }
                    break;
                case "n":
                case "N":
                    if (this.props.isPlaylist && this.props.hasNext && this.props.onNextTrack) {
                        e.preventDefault();
                        this.props.onNextTrack();
                    }
                    break;
                case "Escape":
                    if (this.state.isFullscreen) {
                        e.preventDefault();
                        this.toggleFullscreen();
                    } else if (this.state.showSpeedMenu) {
                        this.state.showSpeedMenu = false;
                    }
                    break;
                case "Home":
                case "0":
                    e.preventDefault();
                    media.currentTime = 0;
                    break;
                case "End":
                    e.preventDefault();
                    media.currentTime = media.duration;
                    break;
                case "<":
                case ",":
                    e.preventDefault();
                    this._cyclePlaybackRate(-1);
                    break;
                case ">":
                case ".":
                    e.preventDefault();
                    this._cyclePlaybackRate(1);
                    break;
            }

            // Numéros 1-9 pour sauter à 10%-90%
            const num = parseInt(e.key);
            if (num >= 1 && num <= 9 && !e.ctrlKey && !e.altKey && !e.metaKey) {
                e.preventDefault();
                media.currentTime = (num / 10) * media.duration;
            }

            this._resetControlsTimer();
        };
        document.addEventListener("keydown", this._keyHandler);
    }

    _setupFullscreenListener() {
        this._fullscreenHandler = () => {
            this.state.isFullscreen = !!document.fullscreenElement;
        };
        document.addEventListener("fullscreenchange", this._fullscreenHandler);
    }

    _setupDoubleClick() {
        if (this.props.isAudio) return;
        // Double-click handled via template t-on-dblclick
    }

    _setupClickOutside() {
        this._clickOutsideHandler = (e) => {
            if (this.state.showSpeedMenu) {
                const speedEl = this.containerRef.el?.querySelector(".yt_player_speed");
                if (speedEl && !speedEl.contains(e.target)) {
                    this.state.showSpeedMenu = false;
                }
            }
        };
        document.addEventListener("click", this._clickOutsideHandler, true);
    }

    // ─── Nettoyage ──────────────────────────────────────────────────────

    _destroy() {
        const media = this.mediaRef.el;
        if (media) {
            media.pause();
            media.removeAttribute("src");
            media.load();
        }
        if (this._keyHandler) {
            document.removeEventListener("keydown", this._keyHandler);
        }
        if (this._fullscreenHandler) {
            document.removeEventListener("fullscreenchange", this._fullscreenHandler);
        }
        if (this._clickOutsideHandler) {
            document.removeEventListener("click", this._clickOutsideHandler, true);
        }
        if (this._controlsTimer) {
            clearTimeout(this._controlsTimer);
        }
    }

    // ─── Formatage ──────────────────────────────────────────────────────

    _formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return "00:00";
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        if (h > 0) {
            return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
        }
        return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }

    // ─── Contrôle de la visibilité des contrôles ────────────────────────

    _resetControlsTimer() {
        this.state.showControls = true;

        if (this._controlsTimer) clearTimeout(this._controlsTimer);

        // Ne masquer que pour la vidéo en lecture
        if (!this.props.isAudio && this.state.isPlaying) {
            this._controlsTimer = setTimeout(() => {
                this.state.showControls = false;
            }, CONTROLS_HIDE_DELAY);
        }
    }

    onContainerMouseMove() {
        this._resetControlsTimer();
    }

    onContainerMouseLeave() {
        if (this.state.isPlaying && !this.props.isAudio) {
            this.state.showControls = false;
            if (this._controlsTimer) clearTimeout(this._controlsTimer);
        }
    }

    // ─── Actions du lecteur ─────────────────────────────────────────────

    togglePlay() {
        const media = this.mediaRef.el;
        if (!media) return;
        if (media.paused) {
            media.play().catch(() => {});
            this._resetControlsTimer();
        } else {
            media.pause();
            this.state.showControls = true;
            if (this._controlsTimer) clearTimeout(this._controlsTimer);
        }
    }

    onSeek(ev) {
        const media = this.mediaRef.el;
        if (!media || !media.duration) return;
        const rect = ev.currentTarget.getBoundingClientRect();
        const x = ev.clientX - rect.left;
        const pct = Math.max(0, Math.min(1, x / rect.width));
        media.currentTime = pct * media.duration;
    }

    onProgressHover(ev) {
        const media = this.mediaRef.el;
        if (!media || !media.duration) return;
        const rect = ev.currentTarget.getBoundingClientRect();
        const x = ev.clientX - rect.left;
        const pct = Math.max(0, Math.min(1, x / rect.width));
        this.state.hoverTime = this._formatTime(pct * media.duration);
        this.state.hoverPosition = (pct * 100);
        this.state.showHoverTime = true;
    }

    onProgressLeave() {
        this.state.showHoverTime = false;
    }

    onVolumeChange(ev) {
        const media = this.mediaRef.el;
        if (!media) return;
        const vol = parseFloat(ev.target.value);
        media.volume = vol;
        media.muted = vol === 0;
        this.state.volume = vol;
        this._savePreference(LS_VOLUME_KEY, vol);
        this._savePreference(LS_MUTED_KEY, vol === 0);
    }

    toggleMute() {
        const media = this.mediaRef.el;
        if (!media) return;
        media.muted = !media.muted;
        this._savePreference(LS_MUTED_KEY, media.muted);
    }

    _adjustVolume(delta) {
        const media = this.mediaRef.el;
        if (!media) return;
        const newVol = Math.max(0, Math.min(1, media.volume + delta));
        media.volume = newVol;
        media.muted = newVol === 0;
        this.state.volume = newVol;
        this._savePreference(LS_VOLUME_KEY, newVol);
    }

    setPlaybackRate(rate) {
        const media = this.mediaRef.el;
        if (!media) return;
        media.playbackRate = rate;
        this.state.playbackRate = rate;
        this.state.showSpeedMenu = false;
        this._savePreference(LS_RATE_KEY, rate);
    }

    _cyclePlaybackRate(direction) {
        const rates = this.playbackRates;
        const idx = rates.indexOf(this.state.playbackRate);
        const newIdx = Math.max(0, Math.min(rates.length - 1, idx + direction));
        this.setPlaybackRate(rates[newIdx]);
    }

    toggleSpeedMenu() {
        this.state.showSpeedMenu = !this.state.showSpeedMenu;
    }

    skipForward() {
        const media = this.mediaRef.el;
        if (!media) return;
        media.currentTime = Math.min(media.currentTime + SKIP_SECONDS, media.duration || 0);
    }

    skipBackward() {
        const media = this.mediaRef.el;
        if (!media) return;
        media.currentTime = Math.max(media.currentTime - SKIP_SECONDS, 0);
    }

    _showSkipFeedback(direction) {
        // Visual feedback handled by CSS animation classes
        const container = this.containerRef.el;
        if (!container) return;
        const cls = direction === "forward" ? "yt_skip_forward_feedback" : "yt_skip_backward_feedback";
        container.classList.add(cls);
        setTimeout(() => container.classList.remove(cls), 500);
    }

    toggleFullscreen() {
        const container = this.containerRef.el;
        if (!container) return;
        if (!document.fullscreenElement) {
            container.requestFullscreen?.().catch(() => {});
        } else {
            document.exitFullscreen?.().catch(() => {});
        }
    }

    onVideoDblClick(ev) {
        ev.preventDefault();
        this.toggleFullscreen();
    }

    async togglePiP() {
        const media = this.mediaRef.el;
        if (!media || this.props.isAudio) return;
        try {
            if (document.pictureInPictureElement) {
                await document.exitPictureInPicture();
            } else {
                await media.requestPictureInPicture();
            }
        } catch (e) {
            console.warn("[Player] PiP error:", e);
        }
    }

    onDownload() {
        const a = document.createElement("a");
        a.href = this.streamUrl;
        // Ajouter l'extension au nom de fichier
        const name = this.props.recordName || "video";
        const hasExt = /\.[a-zA-Z0-9]{2,4}$/.test(name);
        a.download = hasExt ? name : name + (this.props.isAudio ? ".mp3" : ".mp4");
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        this.notification.add("Téléchargement lancé", { type: "info", sticky: false });
    }

    _savePreference(key, value) {
        try {
            localStorage.setItem(key, String(value));
        } catch (e) {
            // silently ignore
        }
    }
}

// ─── Action client : lecteur en mode théâtre ────────────────────────────────
const LS_REPEAT_KEY = "yt_player_repeat";
const LS_SHUFFLE_KEY = "yt_player_shuffle";
const LS_SIDEBAR_KEY = "yt_player_sidebar";
const LS_AUTOPLAY_KEY = "yt_player_autoplay";
const AUTO_NEXT_DELAY = 3; // seconds countdown before auto-next

class YoutubeVideoPlayerAction extends Component {
    static template = "youtube_downloader.VideoPlayerAction";
    static components = { YoutubeVideoPlayer };

    setup() {
        this.sidebarListRef = useRef("sidebarList");

        this.state = useState({
            loaded: false,
            recordData: null,
            // Playlist state
            isPlaylistMode: false,
            playlistName: "",
            playlistTracks: [],
            currentIndex: 0,
            showPlaylistPanel: localStorage.getItem(LS_SIDEBAR_KEY) !== "false",
            repeatMode: localStorage.getItem(LS_REPEAT_KEY) || "none", // none | one | all
            shuffle: localStorage.getItem(LS_SHUFFLE_KEY) === "true",
            autoPlay: localStorage.getItem(LS_AUTOPLAY_KEY) !== "false", // lecture continue par défaut
            shuffleOrder: [],
            // Auto-next countdown
            autoNextCountdown: -1, // -1 = inactive
            // Drag & Drop
            dragIndex: -1,
            dragOverIndex: -1,
            // Whether the player should auto-start
            shouldAutoPlay: false,
        });

        this._autoNextTimer = null;
        this._scrollTimeout = null;

        this._needsScroll = false;

        onMounted(() => this._loadFromContext());
        onPatched(() => {
            if (this._needsScroll) {
                this._needsScroll = false;
                this._doScrollToActive();
            }
        });
        onWillUnmount(() => {
            this._clearAutoNext();
            if (this._scrollTimeout) clearTimeout(this._scrollTimeout);
        });
    }

    _loadFromContext() {
        const ctx = this.props.action?.context || {};
        const recordId = ctx.active_id;
        if (!recordId) return;

        // Check for playlist data
        const tracks = ctx.playlist_tracks;
        const isPlaylist = Array.isArray(tracks) && tracks.length > 1;

        if (isPlaylist) {
            this.state.isPlaylistMode = true;
            this.state.playlistName = ctx.playlist_name || "Liste de lecture";
            this.state.playlistTracks = tracks;
            this.state.currentIndex = ctx.playlist_index || 0;

            // Generate shuffle order
            this._generateShuffleOrder();

            // Load first track
            this._loadTrack(this.state.currentIndex);
        } else {
            // Single track mode (legacy)
            this.state.recordData = {
                id: recordId,
                name: ctx.record_name || "Vidéo",
                isAudio: ctx.is_audio || false,
                streamUrl: ctx.stream_url || "",
                thumbnailUrl: ctx.thumbnail_url || "",
                videoAuthor: ctx.video_author || "",
                videoDuration: ctx.video_duration || "",
                fileSize: ctx.file_size || "",
                quality: ctx.quality || "",
            };
        }
        this.state.loaded = true;
    }

    _loadTrack(index, autoPlay = false) {
        const tracks = this.state.playlistTracks;
        if (index < 0 || index >= tracks.length) return;
        const track = tracks[index];
        this.state.currentIndex = index;
        this.state.shouldAutoPlay = autoPlay;
        this.state.recordData = {
            id: track.id,
            name: track.name || "Vidéo",
            isAudio: track.is_audio || false,
            streamUrl: track.stream_url || "",
            thumbnailUrl: track.thumbnail_url || "",
            videoAuthor: track.video_author || "",
            videoDuration: track.video_duration || "",
            fileSize: track.file_size || "",
            quality: track.quality || "",
        };
        // Auto-scroll to active track in sidebar
        this._scrollToActiveTrack();
    }

    _scrollToActiveTrack() {
        // Flag for onPatched — ensures DOM is updated before scrolling
        this._needsScroll = true;
    }

    _doScrollToActive() {
        if (this._scrollTimeout) clearTimeout(this._scrollTimeout);
        this._scrollTimeout = setTimeout(() => {
            const list = this.sidebarListRef.el;
            if (!list) return;
            const activeItem = list.querySelector(".yt_playlist_item_active");
            if (activeItem) {
                activeItem.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
        }, 50);
    }

    _generateShuffleOrder() {
        const len = this.state.playlistTracks.length;
        const order = Array.from({ length: len }, (_, i) => i);
        // Fisher-Yates shuffle
        for (let i = order.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [order[i], order[j]] = [order[j], order[i]];
        }
        this.state.shuffleOrder = order;
    }

    get hasNext() {
        if (!this.state.isPlaylistMode) return false;
        return this._getNextIndex() >= 0;
    }

    get hasPrev() {
        if (!this.state.isPlaylistMode) return false;
        return this._getPrevIndex() >= 0;
    }

    get repeatIcon() {
        return "fa-repeat";
    }

    get repeatButtonClass() {
        if (this.state.repeatMode === "one") return "yt_theater_ctrl_btn yt_playlist_active";
        if (this.state.repeatMode === "all") return "yt_theater_ctrl_btn yt_playlist_active";
        return "yt_theater_ctrl_btn";
    }

    get repeatTitle() {
        if (this.state.repeatMode === "one") return "Répéter : piste actuelle";
        if (this.state.repeatMode === "all") return "Répéter : toute la liste";
        return "Répéter : désactivé";
    }

    get nextUpTrack() {
        if (!this.state.isPlaylistMode) return null;
        const idx = this._getNextIndex();
        if (idx < 0) return null;
        return this.state.playlistTracks[idx];
    }

    _getNextIndex() {
        const len = this.state.playlistTracks.length;
        if (this.state.shuffle) {
            const shufflePos = this.state.shuffleOrder.indexOf(this.state.currentIndex);
            const nextShufflePos = shufflePos + 1;
            if (nextShufflePos >= len) {
                if (this.state.repeatMode === "all") return this.state.shuffleOrder[0];
                return -1;
            }
            return this.state.shuffleOrder[nextShufflePos];
        }
        const next = this.state.currentIndex + 1;
        if (next >= len) {
            if (this.state.repeatMode === "all") return 0;
            return -1;
        }
        return next;
    }

    _getPrevIndex() {
        const len = this.state.playlistTracks.length;
        if (this.state.shuffle) {
            const shufflePos = this.state.shuffleOrder.indexOf(this.state.currentIndex);
            const prevShufflePos = shufflePos - 1;
            if (prevShufflePos < 0) {
                if (this.state.repeatMode === "all") return this.state.shuffleOrder[len - 1];
                return -1;
            }
            return this.state.shuffleOrder[prevShufflePos];
        }
        const prev = this.state.currentIndex - 1;
        if (prev < 0) {
            if (this.state.repeatMode === "all") return len - 1;
            return -1;
        }
        return prev;
    }

    // ─── Auto-next countdown ────────────────────────────────────────────
    _clearAutoNext() {
        if (this._autoNextTimer) {
            clearInterval(this._autoNextTimer);
            this._autoNextTimer = null;
        }
        this.state.autoNextCountdown = -1;
    }

    cancelAutoNext() {
        this._clearAutoNext();
    }

    skipAutoNext() {
        this._clearAutoNext();
        const next = this._getNextIndex();
        if (next >= 0) {
            this.state.recordData = null;
            setTimeout(() => this._loadTrack(next, true), 50);
        }
    }

    onTrackEnded() {
        if (this.state.repeatMode === "one") {
            const idx = this.state.currentIndex;
            this.state.recordData = null;
            setTimeout(() => this._loadTrack(idx, true), 50);
            return;
        }
        // Si lecture continue désactivée, on s'arrête
        if (!this.state.autoPlay) return;
        const next = this._getNextIndex();
        if (next >= 0) {
            // Start auto-next countdown
            this.state.autoNextCountdown = AUTO_NEXT_DELAY;
            this._autoNextTimer = setInterval(() => {
                this.state.autoNextCountdown--;
                if (this.state.autoNextCountdown <= 0) {
                    this._clearAutoNext();
                    this.state.recordData = null;
                    setTimeout(() => this._loadTrack(next, true), 50);
                }
            }, 1000);
        }
        // else: stop naturally
    }

    nextTrack() {
        if (!this.state.isPlaylistMode) return;
        this._clearAutoNext();
        const next = this._getNextIndex();
        if (next < 0) return;
        this.state.recordData = null;
        setTimeout(() => this._loadTrack(next, true), 50);
    }

    prevTrack() {
        if (!this.state.isPlaylistMode) return;
        this._clearAutoNext();
        const prev = this._getPrevIndex();
        if (prev < 0) return;
        this.state.recordData = null;
        setTimeout(() => this._loadTrack(prev, true), 50);
    }

    playTrackAt(index) {
        if (index === this.state.currentIndex) return;
        this._clearAutoNext();
        this.state.recordData = null;
        setTimeout(() => this._loadTrack(index, true), 50);
    }

    // ─── Track reorder (drag & drop) ────────────────────────────────────
    onDragStart(index, ev) {
        this.state.dragIndex = index;
        ev.dataTransfer.effectAllowed = "move";
        // Minimal drag image
        ev.dataTransfer.setData("text/plain", String(index));
    }

    onDragOver(index, ev) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";
        if (index !== this.state.dragOverIndex) {
            this.state.dragOverIndex = index;
        }
    }

    onDragLeave() {
        // Keep dragOverIndex — it'll be reset on drop/end
    }

    onDrop(index, ev) {
        ev.preventDefault();
        const from = this.state.dragIndex;
        const to = index;
        if (from === to || from < 0) {
            this._resetDrag();
            return;
        }
        // Reorder tracks array
        const tracks = [...this.state.playlistTracks];
        const [moved] = tracks.splice(from, 1);
        tracks.splice(to, 0, moved);
        this.state.playlistTracks = tracks;

        // Update currentIndex to follow the currently playing track
        if (from === this.state.currentIndex) {
            this.state.currentIndex = to;
        } else if (from < this.state.currentIndex && to >= this.state.currentIndex) {
            this.state.currentIndex--;
        } else if (from > this.state.currentIndex && to <= this.state.currentIndex) {
            this.state.currentIndex++;
        }

        // Regenerate shuffle if active
        if (this.state.shuffle) {
            this._generateShuffleOrder();
        }

        this._resetDrag();
    }

    onDragEnd() {
        this._resetDrag();
    }

    _resetDrag() {
        this.state.dragIndex = -1;
        this.state.dragOverIndex = -1;
    }

    moveTrack(index, direction) {
        const newIndex = index + direction;
        if (newIndex < 0 || newIndex >= this.state.playlistTracks.length) return;

        const tracks = [...this.state.playlistTracks];
        [tracks[index], tracks[newIndex]] = [tracks[newIndex], tracks[index]];
        this.state.playlistTracks = tracks;

        // Update currentIndex
        if (index === this.state.currentIndex) {
            this.state.currentIndex = newIndex;
        } else if (newIndex === this.state.currentIndex) {
            this.state.currentIndex = index;
        }

        if (this.state.shuffle) {
            this._generateShuffleOrder();
        }
    }

    removeTrack(index, ev) {
        ev.stopPropagation();
        if (this.state.playlistTracks.length <= 1) return;

        const tracks = [...this.state.playlistTracks];
        tracks.splice(index, 1);
        this.state.playlistTracks = tracks;

        // Adjust currentIndex
        if (index === this.state.currentIndex) {
            // Playing track removed: play the next one (or previous if last)
            const newIdx = Math.min(index, tracks.length - 1);
            this.state.currentIndex = newIdx;
            this.state.recordData = null;
            setTimeout(() => this._loadTrack(newIdx, true), 50);
        } else if (index < this.state.currentIndex) {
            this.state.currentIndex--;
        }

        if (this.state.shuffle) {
            this._generateShuffleOrder();
        }
    }

    // ─── Controls ───────────────────────────────────────────────────────
    toggleRepeat() {
        const modes = ["none", "all", "one"];
        const idx = modes.indexOf(this.state.repeatMode);
        this.state.repeatMode = modes[(idx + 1) % modes.length];
        try { localStorage.setItem(LS_REPEAT_KEY, this.state.repeatMode); } catch (e) { /* ignore */ }
    }

    toggleShuffle() {
        this.state.shuffle = !this.state.shuffle;
        if (this.state.shuffle) {
            this._generateShuffleOrder();
        }
        try { localStorage.setItem(LS_SHUFFLE_KEY, String(this.state.shuffle)); } catch (e) { /* ignore */ }
    }

    toggleAutoPlay() {
        this.state.autoPlay = !this.state.autoPlay;
        // Si on désactive en plein countdown, annuler
        if (!this.state.autoPlay) {
            this._clearAutoNext();
        }
        try { localStorage.setItem(LS_AUTOPLAY_KEY, String(this.state.autoPlay)); } catch (e) { /* ignore */ }
    }

    togglePlaylistPanel() {
        this.state.showPlaylistPanel = !this.state.showPlaylistPanel;
        try { localStorage.setItem(LS_SIDEBAR_KEY, String(this.state.showPlaylistPanel)); } catch (e) { /* ignore */ }
        if (this.state.showPlaylistPanel) {
            this._scrollToActiveTrack();
        }
    }

    close() {
        window.history.back();
    }

    goBack() {
        window.history.back();
    }
}

registry.category("actions").add("youtube_video_player", YoutubeVideoPlayerAction);
