// File input handling
document.addEventListener('DOMContentLoaded', function() {
    // Custom file input display
    const fileInput = document.querySelector('.custom-file-input');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const fileName = e.target.files[0]?.name || 'Choose file';
            const label = document.querySelector('.custom-file-label');
            if (label) {
                label.textContent = fileName;
            }
        });
    }

    // Price validation
    const priceInput = document.querySelector('input[name="price"]');
    if (priceInput) {
        priceInput.addEventListener('input', function(e) {
            const value = e.target.value;
            if (value && !isNaN(value) && parseFloat(value) <= 0) {
                priceInput.setCustomValidity('Price must be greater than zero');
            } else {
                priceInput.setCustomValidity('');
            }
        });
    }

    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Confirmation dialog for buying tickets
    const buyButtons = document.querySelectorAll('.buy-ticket-btn');
    buyButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to purchase this ticket? A 10% commission will be added to the price.')) {
                e.preventDefault();
            }
        });
    });
});
