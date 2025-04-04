// Flash message auto-hide
document.addEventListener('DOMContentLoaded', function() {
    const flashMessages = document.querySelectorAll('.flash-message');
    
    flashMessages.forEach(function(message) {
        setTimeout(function() {
            message.style.opacity = '0';
            setTimeout(function() {
                message.style.display = 'none';
            }, 500); // Wait for fade out animation
        }, 5000); // Display for 5 seconds
    });
    
    // Initialize word count slider if present
    const wordCountSlider = document.getElementById('word_count');
    if (wordCountSlider) {
        updateWordCountLabel(wordCountSlider.value);
        
        // Add styling for the slider
        const sliderStyle = document.createElement('style');
        sliderStyle.textContent = `
            input[type=range] {
                -webkit-appearance: none;
                height: 8px;
                border-radius: 4px;
                background: #e5e7eb;
                outline: none;
            }
            
            input[type=range]::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #7D4BCB;
                cursor: pointer;
            }
            
            input[type=range]::-moz-range-thumb {
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #7D4BCB;
                cursor: pointer;
            }
            
            .range-info {
                font-weight: 500;
            }
            
            #word_count_label {
                color: #7D4BCB;
                font-weight: bold;
            }
        `;
        document.head.appendChild(sliderStyle);
    }
});

// Add smooth transitions to flash messages
document.head.insertAdjacentHTML('beforeend', `
    <style>
        .flash-message {
            transition: opacity 0.5s ease-out;
        }
    </style>
`);

function updateWordCountLabel(value) {
    const label = document.getElementById('word_count_label');
    if (label) {
        label.textContent = value;
    }
} 