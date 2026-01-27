/**
 * Authentication JavaScript
 * 
 * Handles login and registration forms, password validation, and authentication flow.
 */

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check if we're on login or register page
    if (document.getElementById('login-form')) {
        setupLoginForm();
    }
    if (document.getElementById('register-form')) {
        setupRegisterForm();
    }
    
    // Setup password toggles
    setupPasswordToggles();
    
    // Setup forgot password link
    const forgotPasswordLink = document.getElementById('forgot-password-link');
    if (forgotPasswordLink) {
        forgotPasswordLink.addEventListener('click', (e) => {
            e.preventDefault();
            const email = prompt('Enter the email address associated with your account to request a reset link:');
            if (!email) {
                return;
            }
            (async () => {
                try {
                    await JobTracker.apiCall('/auth/password/reset-request', {
                        method: 'POST',
                        body: JSON.stringify({ email })
                    });
                    JobTracker.showNotification(
                        'If an account exists for that email, a reset link has been generated. Check your inbox.',
                        'info',
                        5000
                    );
                } catch (error) {
                    console.error('Password reset request error:', error);
                    JobTracker.showNotification('Unable to request password reset right now. Please try again later.', 'error');
                }
            })();
        });
    }
});

/**
 * Setup login form
 */
function setupLoginForm() {
    const form = document.getElementById('login-form');
    const submitBtn = document.getElementById('login-submit-btn');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;
        const rememberMe = document.getElementById('remember-me').checked;
        
        // Clear previous errors
        clearErrors();
        
        // Validate
        if (!username || !password) {
            showError('Please fill in all required fields');
            return;
        }
        
        // Disable submit button
        submitBtn.disabled = true;
        submitBtn.textContent = 'Signing in...';
        
        try {
            const response = await JobTracker.apiCall('/auth/login', {
                method: 'POST',
                body: JSON.stringify({
                    username,
                    password,
                    remember_me: rememberMe
                })
            });
            
            // Store token and user info
            JobTracker.setAuthToken(response.session_token, response.user);
            
            // Show success message
            JobTracker.showNotification('Login successful!', 'success');
            
            // Redirect to dashboard or previous page
            const redirectTo = new URLSearchParams(window.location.search).get('redirect') || '/';
            setTimeout(() => {
                window.location.href = redirectTo;
            }, 500);
        } catch (error) {
            console.error('Login error:', error);
            showError(error.message || 'Invalid username or password');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Sign In';
        }
    });
}

/**
 * Setup registration form
 */
function setupRegisterForm() {
    const form = document.getElementById('register-form');
    const submitBtn = document.getElementById('register-submit-btn');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirm-password');
    
    // Real-time password validation
    passwordInput.addEventListener('input', () => {
        validatePasswordStrength(passwordInput.value);
        validatePasswordMatch();
    });
    
    confirmPasswordInput.addEventListener('input', () => {
        validatePasswordMatch();
    });
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const username = document.getElementById('username').value.trim();
        const email = document.getElementById('email').value.trim();
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        const terms = document.getElementById('terms').checked;
        
        // Clear previous errors
        clearErrors();
        
        // Validate
        if (!username || !password || !confirmPassword) {
            showError('Please fill in all required fields');
            return;
        }
        
        if (!terms) {
            showError('You must agree to the Terms of Service and Privacy Policy');
            return;
        }
        
        // Validate password strength
        const passwordValid = validatePasswordStrength(password);
        if (!passwordValid) {
            showError('Password does not meet requirements');
            return;
        }
        
        // Validate password match
        if (password !== confirmPassword) {
            showError('Passwords do not match');
            document.getElementById('confirm-password-error').textContent = 'Passwords do not match';
            document.getElementById('confirm-password-error').classList.add('show');
            return;
        }
        
        // Disable submit button
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating account...';
        
        try {
            const response = await JobTracker.apiCall('/auth/register', {
                method: 'POST',
                body: JSON.stringify({
                    username,
                    email: email || null,
                    password
                })
            });
            
            // Store token and user info
            JobTracker.setAuthToken(response.session_token, response.user);
            
            // Show success message
            JobTracker.showNotification('Account created successfully!', 'success');
            
            // Redirect to dashboard
            setTimeout(() => {
                window.location.href = '/';
            }, 500);
        } catch (error) {
            console.error('Registration error:', error);
            showError(error.message || 'Failed to create account. Please try again.');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Create Account';
        }
    });
}

/**
 * Validate password strength and update UI
 */
function validatePasswordStrength(password) {
    // Check byte length (bcrypt has 72-byte limit)
    const passwordBytes = new TextEncoder().encode(password);
    const byteLengthValid = passwordBytes.length <= 72;
    
    const requirements = {
        length: password.length >= 8 && byteLengthValid,
        uppercase: /[A-Z]/.test(password),
        lowercase: /[a-z]/.test(password),
        digit: /\d/.test(password),
        special: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password)
    };
    
    // Update requirement indicators
    document.getElementById('req-length').classList.toggle('valid', requirements.length);
    if (!byteLengthValid && password.length >= 8) {
        // Show warning if password exceeds byte limit
        const lengthEl = document.getElementById('req-length');
        lengthEl.textContent = `At least 8 characters (max 72 bytes - currently ${passwordBytes.length} bytes)`;
        lengthEl.classList.remove('valid');
    } else if (password.length >= 8 && byteLengthValid) {
        document.getElementById('req-length').textContent = 'At least 8 characters (max 72 bytes)';
    }
    document.getElementById('req-uppercase').classList.toggle('valid', requirements.uppercase);
    document.getElementById('req-lowercase').classList.toggle('valid', requirements.lowercase);
    document.getElementById('req-digit').classList.toggle('valid', requirements.digit);
    document.getElementById('req-special').classList.toggle('valid', requirements.special);
    
    // Return true if all requirements met
    return Object.values(requirements).every(req => req === true);
}

/**
 * Validate password match
 */
function validatePasswordMatch() {
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    const errorEl = document.getElementById('confirm-password-error');
    
    if (confirmPassword && password !== confirmPassword) {
        errorEl.textContent = 'Passwords do not match';
        errorEl.classList.add('show');
        return false;
    } else {
        errorEl.classList.remove('show');
        return true;
    }
}

/**
 * Setup password visibility toggles
 */
function setupPasswordToggles() {
    document.querySelectorAll('.password-toggle').forEach(toggle => {
        toggle.addEventListener('click', () => {
            const input = toggle.previousElementSibling || toggle.parentElement.querySelector('input[type="password"], input[type="text"]');
            
            if (input.type === 'password') {
                input.type = 'text';
            } else {
                input.type = 'password';
            }
            
            // Keep the existing SVG icon markup; only the input type changes.
            // Screen readers rely on the aria-label on the button itself.
        });
    });
}

/**
 * Show error message
 */
function showError(message) {
    const errorEl = document.getElementById('error-message');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    } else {
        JobTracker.showNotification(message, 'error');
    }
}

/**
 * Clear all error messages
 */
function clearErrors() {
    document.querySelectorAll('.error-message').forEach(el => {
        el.classList.remove('show');
        el.textContent = '';
    });
    
    const globalError = document.getElementById('error-message');
    if (globalError) {
        globalError.style.display = 'none';
    }
}
