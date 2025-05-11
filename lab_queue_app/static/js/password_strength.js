document.addEventListener('DOMContentLoaded', function() {
    const passwordInput = document.getElementById('id_password1');
    const strengthMeter = document.createElement('div');
    strengthMeter.id = 'password-strength';
    passwordInput.parentNode.appendChild(strengthMeter);

    passwordInput.addEventListener('input', function() {
        const password = passwordInput.value;
        let strength = 0;
        
        if (password.length >= 8) strength++;
        if (password.length >= 12) strength++;
        
        if (/[A-Z]/.test(password)) strength++;
        if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) strength++;
        
        const messages = [
            'Очень слабый',
            'Слабый', 
            'Средний',
            'Хороший',
            'Отличный'
        ];
        strengthMeter.textContent = `Надёжность: ${messages[strength] || ''}`;
        strengthMeter.className = `strength-${strength}`;
    });
});
