/** @odoo-module **/
/**
 * YouTube Downloader — JavaScript Odoo 17
 * Polling automatique de la progression des téléchargements
 * Amélioré avec notifications, polling intelligent et gestion d'erreurs
 */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { onWillUnmount, onMounted } from "@odoo/owl";

// ─── Configuration ───────────────────────────────────────────────────────────
const POLL_INTERVAL = 2500; // ms
const POLL_INTERVAL_SLOW = 5000; // ms (quand en attente)
const MAX_POLL_ERRORS = 5;

// ─── Polling de progression sur le formulaire ────────────────────────────────
patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);

        if (this.props.resModel !== "youtube.download") return;

        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this._pollingInterval = null;
        this._pollErrors = 0;
        this._lastState = null;

        onMounted(() => this._startPollingIfNeeded());
        onWillUnmount(() => this._stopPolling());
    },

    async _startPollingIfNeeded() {
        if (!this.model?.root?.data) return;
        const state = this.model.root.data.state;
        if (state === "downloading" || state === "pending") {
            this._lastState = state;
            this._startPolling(state === "pending" ? POLL_INTERVAL_SLOW : POLL_INTERVAL);
        }
    },

    _startPolling(interval = POLL_INTERVAL) {
        if (this._pollingInterval) return;
        this._pollErrors = 0;
        this._pollingInterval = setInterval(async () => {
            await this._pollStatus();
        }, interval);
    },

    _stopPolling() {
        if (this._pollingInterval) {
            clearInterval(this._pollingInterval);
            this._pollingInterval = null;
        }
    },

    async _pollStatus() {
        if (!this.model?.root?.data?.id) return;
        const recordId = this.model.root.data.id;

        try {
            const result = await this.rpc(
                `/youtube_downloader/check_status/${recordId}`, {}
            );

            if (!result || result.error) {
                this._pollErrors++;
                if (this._pollErrors >= MAX_POLL_ERRORS) {
                    this._stopPolling();
                }
                return;
            }

            this._pollErrors = 0;

            // Mise à jour de la progression dans l'UI
            const progressBar = document.getElementById("yt_progress_bar");
            const progressText = document.getElementById("yt_progress_text");
            if (progressBar) {
                progressBar.style.width = `${result.progress}%`;
                progressBar.setAttribute("aria-valuenow", result.progress);
            }
            if (progressText) {
                progressText.textContent = `${result.progress}%`;
            }

            // Détection du changement d'état pending -> downloading
            if (this._lastState === "pending" && result.state === "downloading") {
                this._stopPolling();
                this._startPolling(POLL_INTERVAL);
                this.notification.add(
                    `📥 Téléchargement démarré : ${result.name}`,
                    { type: "info", title: "Téléchargement en cours", sticky: false }
                );
            }
            this._lastState = result.state;

            // Téléchargement terminé
            if (result.state === "done") {
                this._stopPolling();
                this.notification.add(
                    `✅ Téléchargement terminé : ${result.name} (${result.file_size})`,
                    { type: "success", title: "Terminé", sticky: false }
                );
                await this.model.root.load();
            }
            // Erreur
            else if (result.state === "error") {
                this._stopPolling();
                const retryInfo = result.retry_count > 0
                    ? ` (tentative ${result.retry_count}/${result.max_retries})`
                    : "";
                this.notification.add(
                    `❌ Erreur${retryInfo} : ${result.error_message || "Erreur inconnue"}`,
                    { type: "danger", title: "Échec du téléchargement", sticky: true }
                );
                await this.model.root.load();
            }
        } catch (e) {
            this._pollErrors++;
            console.warn("[YouTubeDownloader] Polling error:", e);
            if (this._pollErrors >= MAX_POLL_ERRORS) {
                this._stopPolling();
                console.error("[YouTubeDownloader] Arrêt du polling après trop d'erreurs.");
            }
        }
    },
});

// ─── Rafraîchissement automatique de la liste ───────────────────────────
patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);

        if (this.props.resModel !== "youtube.download") return;

        this._listPollingInterval = null;

        onMounted(() => {
            this._listPollingInterval = setInterval(async () => {
                try {
                    await this.model.root.load();
                } catch (e) {
                    // Ignorer les erreurs silencieuses
                }
            }, 10000); // Toutes les 10 secondes
        });

        onWillUnmount(() => {
            if (this._listPollingInterval) {
                clearInterval(this._listPollingInterval);
                this._listPollingInterval = null;
            }
        });
    },
});

// ─── Utilitaire : vérification yt-dlp au chargement ───────────────────────
const checkYtDlp = async (rpc) => {
    try {
        const res = await rpc("/web/dataset/call_kw", {
            model: "youtube.download",
            method: "check_ytdlp_installed",
            args: [],
            kwargs: {},
        });
        if (!res.installed) {
            console.warn(
                "[YouTubeDownloader] yt-dlp n'est pas installé. "
                + "Installez-le avec : pip install yt-dlp"
            );
        } else {
            console.info(`[YouTubeDownloader] yt-dlp v${res.version} détecté ✅`);
        }
    } catch (e) {
        console.warn("[YouTubeDownloader] Impossible de vérifier yt-dlp:", e);
    }
};
