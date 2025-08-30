/** @odoo-module **/

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { registry } from "@web/core/registry";
import { onWillUnmount } from "@odoo/owl";

export class KidsDashboardController extends KanbanController {
    setup() {
        super.setup();
        this.updateInterval = null;
        this.refreshInterval = null;
        this.isDestroyed = false;
        
        // Use OWL's lifecycle hook for proper cleanup
        onWillUnmount(() => {
            this.isDestroyed = true;
            this.clearIntervals();
        });
        
        this.startRealTimeUpdates();
    }

    startRealTimeUpdates() {
        // Update timers every second
        this.updateInterval = setInterval(() => {
            if (this.isDestroyed) {
                this.clearIntervals();
                return;
            }
            
            if (this.env && !this.env.isDestroyed && this.__owl__ && this.__owl__.status !== 'destroyed') {
                try {
                    this.updateTimers();
                } catch (error) {
                    console.warn('Timer update failed:', error);
                    this.clearIntervals();
                }
            }
        }, 1000);

        // Refresh data every 30 seconds - DISABLED to prevent component destruction errors
        // this.refreshInterval = setInterval(() => {
        //     if (this.isDestroyed) {
        //         this.clearIntervals();
        //         return;
        //     }
            
        //     if (this.model && this.env && !this.env.isDestroyed && this.__owl__ && this.__owl__.status !== 'destroyed') {
        //         try {
        //             this.model.load();
        //         } catch (error) {
        //             console.warn('Model load failed:', error);
        //             this.clearIntervals();
        //         }
        //     }
        // }, 30000);
    }

    clearIntervals() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    updateTimers() {
        const cards = document.querySelectorAll('.o_kids_checkin_card');
        cards.forEach(card => {
            const checkinTime = card.dataset.checkinTime;
            if (checkinTime) {
                const checkinDate = new Date(checkinTime);
                const now = new Date();
                const diffMs = now - checkinDate;
                const diffMinutes = Math.floor(diffMs / (1000 * 60));
                const hours = Math.floor(diffMinutes / 60);
                const minutes = diffMinutes % 60;
                
                // Update timer display
                const timerDisplay = card.querySelector('.timer-display');
                if (timerDisplay) {
                    timerDisplay.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                }

                // Update duration display
                const durationDisplay = card.querySelector('.live-duration');
                if (durationDisplay) {
                    durationDisplay.textContent = `${diffMinutes} min`;
                }

                // Update progress bar
                const progressBar = card.querySelector('.time-progress');
                if (progressBar) {
                    const freeMinutes = parseInt(progressBar.dataset.freeMinutes) || 0;
                    const extraMinutes = parseInt(progressBar.dataset.extraMinutes) || 0;
                    const totalAllowed = freeMinutes + 60; // Assume 60 min base allowance
                    const progressPercent = Math.min((diffMinutes / totalAllowed) * 100, 100);
                    progressBar.style.width = `${progressPercent}%`;
                    
                    // Change color based on time usage
                    if (extraMinutes > 0) {
                        progressBar.classList.remove('bg-success');
                        progressBar.classList.add('bg-warning');
                    } else if (diffMinutes > freeMinutes * 0.8) {
                        progressBar.classList.remove('bg-success');
                        progressBar.classList.add('bg-info');
                    }
                }

                // Add pulsing effect for overtime
                if (diffMinutes > 120) { // More than 2 hours
                    card.classList.add('overtime-alert');
                } else {
                    card.classList.remove('overtime-alert');
                }
            }
        });
    }

    willUnmount() {
        this.isDestroyed = true;
        this.clearIntervals();
        super.willUnmount();
    }
}

export class KidsDashboardRenderer extends KanbanRenderer {
    setup() {
        super.setup();
    }
}

export const kidsDashboardView = {
    ...kanbanView,
    Controller: KidsDashboardController,
    Renderer: KidsDashboardRenderer,
};

registry.category("views").add("kids_dashboard_kanban", kidsDashboardView);
