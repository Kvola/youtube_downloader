/** @odoo-module **/
/**
 * YouTube Downloader — Dashboard OWL Component (Odoo 17)
 * Version professionnelle avec graphiques, insights et suivi en temps réel
 */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";

export class YoutubeDashboard extends Component {
    static template = "youtube_downloader.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            data: null,
            loading: true,
        });
        this._refreshInterval = null;
        this._activeRefreshInterval = null;

        onWillStart(async () => {
            await this._loadData();
        });

        onMounted(() => {
            // Rafraîchir le dashboard toutes les 30 secondes
            this._refreshInterval = setInterval(() => this._loadData(), 30000);
            // Si téléchargements actifs, rafraîchir toutes les 5 secondes
            this._activeRefreshInterval = setInterval(() => {
                if (this.state.data && this.state.data.in_progress > 0) {
                    this._loadData();
                }
            }, 5000);
        });

        onWillUnmount(() => {
            if (this._refreshInterval) clearInterval(this._refreshInterval);
            if (this._activeRefreshInterval) clearInterval(this._activeRefreshInterval);
        });
    }

    async _loadData() {
        try {
            const data = await this.orm.call(
                "youtube.download",
                "get_dashboard_data",
                [],
            );
            this.state.data = data;
            this.state.loading = false;
        } catch (e) {
            console.error("[YouTubeDashboard] Erreur chargement:", e);
            this.state.loading = false;
        }
    }

    async onRefresh() {
        this.state.loading = true;
        await this._loadData();
    }

    // ─── Navigation actions ────────────────────────────────────────────

    onClickTotal() {
        this.action.doAction("youtube_downloader.action_youtube_download_all");
    }

    onClickDone() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Téléchargements terminés",
            res_model: "youtube.download",
            view_mode: "tree,kanban,form",
            domain: [["state", "=", "done"]],
        });
    }

    onClickErrors() {
        this.action.doAction("youtube_downloader.action_youtube_download_errors");
    }

    onClickInProgress() {
        this.action.doAction("youtube_downloader.action_youtube_download_active");
    }

    onClickDrafts() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Brouillons",
            res_model: "youtube.download",
            view_mode: "tree,kanban,form",
            domain: [["state", "=", "draft"]],
        });
    }

    onClickNewDownload() {
        this.action.doAction("youtube_downloader.action_youtube_download_wizard");
    }

    onClickRetryErrors() {
        this.orm.call("youtube.download", "action_retry_all_errors", [[]]).then(() => {
            this._loadData();
        });
    }

    onClickRecord(recordId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Téléchargement",
            res_model: "youtube.download",
            res_id: recordId,
            view_mode: "form",
            views: [[false, "form"]],
        });
    }

    // ─── Computed properties for template ──────────────────────────────

    get qualityLabels() {
        if (!this.state.data || !this.state.data.quality_stats) return [];
        return Object.entries(this.state.data.quality_stats);
    }

    get formatLabels() {
        if (!this.state.data || !this.state.data.format_stats) return [];
        return Object.entries(this.state.data.format_stats);
    }

    get topAuthors() {
        if (!this.state.data || !this.state.data.top_authors) return [];
        return this.state.data.top_authors;
    }

    get successRateColor() {
        if (!this.state.data) return "yt_rate_neutral";
        const rate = this.state.data.success_rate;
        if (rate >= 90) return "yt_rate_excellent";
        if (rate >= 70) return "yt_rate_good";
        return "yt_rate_poor";
    }

    get successRateBarClass() {
        if (!this.state.data) return "";
        const rate = this.state.data.success_rate;
        if (rate >= 90) return "yt_fill_excellent";
        if (rate >= 70) return "yt_fill_good";
        return "yt_fill_poor";
    }

    get successRateWidth() {
        if (!this.state.data) return "0%";
        return `${this.state.data.success_rate}%`;
    }

    // Graphique à barres — données avec hauteur calculée
    get chartData() {
        if (!this.state.data || !this.state.data.daily_chart) return [];
        const chart = this.state.data.daily_chart;
        const maxCount = Math.max(...chart.map(d => d.count), 1);
        return chart.map(d => ({
            ...d,
            height: Math.max((d.count / maxCount) * 100, d.count > 0 ? 8 : 3),
        }));
    }

    // Audio vs Vidéo percentages
    get videoPercent() {
        if (!this.state.data || this.state.data.done === 0) return 0;
        return Math.round((this.state.data.video_count / this.state.data.done) * 100);
    }

    get audioPercent() {
        if (!this.state.data || this.state.data.done === 0) return 0;
        return Math.round((this.state.data.audio_count / this.state.data.done) * 100);
    }

    // Calcule la largeur de barre proportionnelle pour les stats qualité/format
    getBarWidth(count) {
        if (!this.state.data) return 0;
        const total = this.state.data.done || 1;
        return Math.max(Math.round((count / total) * 100), 5);
    }
}

registry.category("actions").add("youtube_downloader.dashboard", YoutubeDashboard);
