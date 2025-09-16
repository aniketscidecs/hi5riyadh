// Simple Dashboard Timer - Loads automatically
(function() {
    'use strict';
    
    console.log('🚀 Kids Dashboard Timer Loading...');
    
    let timerInterval = null;
    
    function startTimer() {
        // Clear any existing timer
        if (timerInterval) {
            clearInterval(timerInterval);
        }
        
        console.log('✅ Kids Timer Started - Countdown/Positive Format');
        
        // Update every second
        timerInterval = setInterval(function() {
            updateAllTimers();
        }, 1000);
        
        // Update immediately first
        updateAllTimers();
    }
    
    function updateAllTimers() {
        // Only run on dashboard pages
        if (!window.location.href.includes('dashboard') && !document.querySelector('td[name="live_timer"]')) {
            return;
        }
        
        const timerCells = document.querySelectorAll('td[name="live_timer"]');
        
        if (timerCells.length === 0) {
            return;
        }
        
        timerCells.forEach(function(timerCell) {
            const row = timerCell.closest('tr');
            const checkinCell = row ? row.querySelector('td[name="checkin_time"]') : null;
            const stateField = row ? row.querySelector('td[name="state"]') : null;
            const extraMinutesCell = row ? row.querySelector('td[name="extra_minutes"]') : null;
            const allowedMinutesCell = row ? row.querySelector('td[name="allowed_minutes"]') : null;
            
            // Only update timer if child is checked in
            const isCheckedIn = stateField && stateField.textContent.trim() === 'Checked In';
            
            if (checkinCell && isCheckedIn) {
                const checkinText = checkinCell.textContent.trim();
                if (checkinText) {
                    const checkinTime = parseDateTime(checkinText);
                    if (checkinTime) {
                        const now = new Date();
                        const duration = now - checkinTime;
                        
                        // Get dynamic allowed minutes from the row
                        const allowedMinutesText = allowedMinutesCell?.textContent?.trim();
                        let allowedMinutes = 1; // Default to 1 minute instead of 60
                        
                        if (allowedMinutesCell && allowedMinutesText && !isNaN(parseInt(allowedMinutesText))) {
                            allowedMinutes = parseInt(allowedMinutesText);
                            console.log('✅ Using package allowed minutes:', allowedMinutes);
                        } else {
                            console.warn('⚠️ Could not read allowed_minutes field, using 1 minute default');
                        }
                        
                        const formatted = calculateCountdownFormat(duration, allowedMinutes);
                        
                        // Update the timer display
                        timerCell.textContent = formatted;
                        
                        // Apply styling
                        timerCell.style.fontFamily = 'monospace';
                        timerCell.style.fontWeight = 'bold';
                        timerCell.style.textAlign = 'center';
                        timerCell.style.minWidth = '120px';
                        
                        // Color coding
                        if (formatted.startsWith('-')) {
                            // Countdown time (still in free time)
                            timerCell.style.color = '#28a745'; // Green
                            timerCell.style.animation = 'none';
                        } else if (formatted.startsWith('+')) {
                            // Extra time
                            const extraMinutes = extraMinutesCell ? parseInt(extraMinutesCell.textContent.trim()) || 0 : 0;
                            if (extraMinutes <= 10) {
                                timerCell.style.color = '#ffc107'; // Yellow
                                timerCell.style.animation = 'none';
                            } else {
                                timerCell.style.color = '#dc3545'; // Red
                                timerCell.style.animation = 'pulse 1s infinite';
                            }
                        }
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
    
    function calculateCountdownFormat(durationMs, allowedMinutes = 1) {
        // Use dynamic allowed time from package configuration
        const allowedMs = allowedMinutes * 60 * 1000;
        
        const totalSec = Math.floor(durationMs / 1000);
        const allowedSec = Math.floor(allowedMs / 1000);
        
        let displaySec, prefix;
        
        if (totalSec <= allowedSec) {
            // Still within allowed time - show countdown
            displaySec = allowedSec - totalSec;
            prefix = '-';
        } else {
            // Over allowed time - show extra time
            displaySec = totalSec - allowedSec;
            prefix = '+';
        }
        
        const hours = Math.floor(displaySec / 3600);
        const minutes = Math.floor((displaySec % 3600) / 60);
        const seconds = displaySec % 60;
        
        return prefix + hours.toString().padStart(2, '0') + ':' + 
               minutes.toString().padStart(2, '0') + ':' + 
               seconds.toString().padStart(2, '0');
    }
    
    // Initialize timer when DOM is ready
    function initTimer() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(startTimer, 1000);
            });
        } else {
            setTimeout(startTimer, 1000);
        }
    }
    
    // Start the timer
    initTimer();
    
    // Also restart on page navigation
    if (window.addEventListener) {
        window.addEventListener('hashchange', function() {
            setTimeout(startTimer, 1000);
        });
    }
    
    // Add CSS for pulse animation
    if (!document.getElementById('dashboard-timer-styles')) {
        const style = document.createElement('style');
        style.id = 'dashboard-timer-styles';
        style.textContent = `
            @keyframes pulse {
                0% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.7; transform: scale(1.05); }
                100% { opacity: 1; transform: scale(1); }
            }
        `;
        document.head.appendChild(style);
    }
    
})();
