// Simple Kids Dashboard Timer - No complex Odoo dependencies
// This will work immediately when loaded

console.log('🚀 Kids Dashboard Timer Loading...');

// Start timer immediately when script loads
(function() {
    'use strict';
    
    let timerInterval = null;
    
    function startTimer() {
        // Clear any existing timer
        if (timerInterval) {
            clearInterval(timerInterval);
        }
        
        console.log('✅ Kids Timer Started - Updating every 100ms');
        
        // Update immediately first
        updateAllTimers();
        
        // Then update every 100ms for smooth millisecond display
        timerInterval = setInterval(function() {
            updateAllTimers();
        }, 100);
    }
    
    function updateAllTimers() {
        // Find all timer cells in the dashboard
        const timerCells = document.querySelectorAll('td[name="live_timer"]');
        
        if (timerCells.length === 0) {
            console.log('⚠️ No timer cells found');
            return;
        }
        
        console.log(`🔄 Updating ${timerCells.length} timer(s)`);
        
        timerCells.forEach(function(timerCell) {
            // Find the corresponding check-in time cell in the same row
            const row = timerCell.closest('tr');
            const checkinCell = row ? row.querySelector('td[name="checkin_time"]') : null;
            const stateField = row ? row.querySelector('td[name="state"]') : null;
            // Only update timer if child is actually checked in (using state field)
            const isCheckedIn = stateField && stateField.textContent.trim() === 'Checked In';
            
            if (checkinCell && isCheckedIn) {
                const checkinText = checkinCell.textContent.trim();
                if (checkinText) {
                    const checkinTime = parseDateTime(checkinText);
                    if (checkinTime) {
                        const now = new Date();
                        const duration = now - checkinTime;
                        const formatted = formatWithMilliseconds(duration);
                        
                        // Update the timer display
                        timerCell.textContent = formatted;
                        
                        // Apply styling
                        timerCell.style.fontFamily = 'monospace';
                        timerCell.style.fontWeight = 'bold';
                        timerCell.style.textAlign = 'center';
                        
                        // Color coding based on duration
                        const minutes = duration / (1000 * 60);
                        if (minutes < 5) {
                            timerCell.style.color = '#28a745'; // Green
                        } else if (minutes < 10) {
                            timerCell.style.color = '#ffc107'; // Yellow
                        } else {
                            timerCell.style.color = '#dc3545'; // Red
                            timerCell.style.fontWeight = 'bold';
                        }
                        
                        // Also update extra time field if it exists
                        updateExtraTimeField(row, duration);
                    }
                }
            }
        });
    }
    
    function parseDateTime(timeStr) {
        try {
            const clean = timeStr.replace(/\s+/g, ' ').trim();
            let date = new Date(clean);
            
            if (isNaN(date.getTime())) {
                // Try DD/MM/YYYY HH:MM:SS format
                const parts = clean.match(/(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2}):(\d{2})/);
                if (parts) {
                    const [, day, month, year, hour, minute, second] = parts;
                    date = new Date(year, month - 1, day, hour, minute, second);
                }
            }
            
            return isNaN(date.getTime()) ? null : date;
        } catch (e) {
            return null;
        }
    }
    
    function formatWithMilliseconds(ms) {
        const totalSec = Math.floor(ms / 1000);
        const centisec = Math.floor((ms % 1000) / 10);
        
        const hours = Math.floor(totalSec / 3600);
        const minutes = Math.floor((totalSec % 3600) / 60);
        const seconds = totalSec % 60;
        
        if (hours > 0) {
            return hours.toString().padStart(2, '0') + ':' + 
                   minutes.toString().padStart(2, '0') + ':' + 
                   seconds.toString().padStart(2, '0') + '.' + 
                   centisec.toString().padStart(2, '0');
        } else {
            return minutes.toString().padStart(2, '0') + ':' + 
                   seconds.toString().padStart(2, '0') + '.' + 
                   centisec.toString().padStart(2, '0');
        }
    }
    
    function updateExtraTimeField(row, duration) {
        const extraTimeCell = row ? row.querySelector('td[name="extra_minutes"]') : null;
        
        if (extraTimeCell) {
            // Calculate extra minutes (assuming 1 minute = 60000ms daily free time + 0 margin)
            // You can adjust these values based on the package settings
            const dailyFreeMinutes = 1; // Default from package
            const marginMinutes = 0;    // Default from package
            
            const totalMinutes = Math.floor(duration / (1000 * 60));
            const freeAllowance = dailyFreeMinutes + marginMinutes;
            const extraMinutes = Math.max(0, totalMinutes - freeAllowance);
            
            // Update the extra time display
            extraTimeCell.textContent = extraMinutes;
            
            // Color coding for extra time
            if (extraMinutes > 0) {
                extraTimeCell.style.color = '#dc3545'; // Red for overtime
                extraTimeCell.style.fontWeight = 'bold';
            } else {
                extraTimeCell.style.color = '#28a745'; // Green for within limits
                extraTimeCell.style.fontWeight = 'normal';
            }
        }
    }
    
    // Initialize timer when DOM is ready
    function initTimer() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', startTimer);
        } else {
            // DOM is already ready, start immediately
            setTimeout(startTimer, 500);
        }
    }
    
    // Start the initialization
    initTimer();
    
    // Also restart timer when page changes (for SPA navigation)
    if (window.addEventListener) {
        window.addEventListener('hashchange', function() {
            setTimeout(startTimer, 1000);
        });
    }
    
    console.log('📊 Kids Dashboard Timer Script Loaded');
    
})();

// Also expose a global function to manually start the timer
window.startKidsTimer = function() {
    console.log(' Manually starting Kids Timer...');
    startTimer();
};
