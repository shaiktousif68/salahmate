/**
 * Dashboard functionality
 */

// Mobile sidebar toggle
document.addEventListener('DOMContentLoaded', function() {
    // Check if we need a mobile menu button
    if (window.innerWidth <= 768) {
        const sidebar = document.querySelector('.sidebar');
        const mainContent = document.querySelector('.main-content');

        if (sidebar && mainContent) {
            const toggleBtn = document.createElement('button');
            toggleBtn.className = 'btn btn-outline mobile-menu-btn';
            toggleBtn.innerHTML = '<i class="fas fa-bars"></i> Menu';
            toggleBtn.style.position = 'fixed';
            toggleBtn.style.top = '1rem';
            toggleBtn.style.left = '1rem';
            toggleBtn.style.zIndex = '2000';
            document.body.appendChild(toggleBtn);

            toggleBtn.addEventListener('click', function() {
                sidebar.classList.toggle('open');
            });

            mainContent.addEventListener('click', function(e) {
                if (sidebar.classList.contains('open') && !e.target.closest('.sidebar')) {
                    sidebar.classList.remove('open');
                }
            });
        }
    }

    // Initialize Three.js background AFTER the page is fully rendered and
    // idle — the particles are decorative polish and must not block the
    // first paint or compete with content for the main thread.
    if ('requestIdleCallback' in window) {
        requestIdleCallback(() => initParticlesBackground(), { timeout: 2000 });
    } else {
        setTimeout(() => initParticlesBackground(), 300);
    }
});

/**
 * Initialize Three.js floating particles background
 */
function initParticlesBackground() {
    const container = document.getElementById('particles-bg');
    if (!container || typeof THREE === 'undefined') return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });

    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Create particles
    const particleCount = 50;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    const emerald = new THREE.Color(0x10b981);
    const gold = new THREE.Color(0xd4af37);

    for (let i = 0; i < particleCount; i++) {
        positions[i * 3] = (Math.random() - 0.5) * 20;
        positions[i * 3 + 1] = (Math.random() - 0.5) * 20;
        positions[i * 3 + 2] = (Math.random() - 0.5) * 20;

        const color = Math.random() > 0.5 ? emerald : gold;
        colors[i * 3] = color.r;
        colors[i * 3 + 1] = color.g;
        colors[i * 3 + 2] = color.b;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
        size: 0.08,
        vertexColors: true,
        transparent: true,
        opacity: 0.6,
        blending: THREE.AdditiveBlending
    });

    const particles = new THREE.Points(geometry, material);
    scene.add(particles);

    camera.position.z = 5;

    // Animation
    let mouseX = 0;
    let mouseY = 0;

    document.addEventListener('mousemove', (e) => {
        mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
        mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
    });

    function animate() {
        requestAnimationFrame(animate);

        particles.rotation.y += 0.0005;
        particles.rotation.x += 0.0002;

        // Parallax effect
        camera.position.x += (mouseX * 0.5 - camera.position.x) * 0.05;
        camera.position.y += (-mouseY * 0.5 - camera.position.y) * 0.05;
        camera.lookAt(scene.position);

        renderer.render(scene, camera);
    }

    animate();

    // Handle resize
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
}

/**
 * Show a toast notification
 * @param {string} message - The message to display
 * @param {string} type - The type of notification (success, danger, warning, info)
 */
function showToast(message, type = 'success') {
    let container = document.querySelector('.toast-container-salahmate');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container-salahmate';
        Object.assign(container.style, {
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            zIndex: '10000',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
        });
        document.body.appendChild(container);
    }

    const icons = {
        success: '<i class="fas fa-check-circle"></i>',
        danger: '<i class="fas fa-times-circle"></i>',
        warning: '<i class="fas fa-exclamation-triangle"></i>',
        info: '<i class="fas fa-info-circle"></i>'
    };
    const iconHTML = icons[type] || icons.info;

    const toast = document.createElement('div');
    toast.className = `alert alert-${type} glass-panel`; // Keep original classes for consistency
    toast.innerHTML = `${iconHTML} <span style="margin-left: 10px;">${message}</span>`;

    Object.assign(toast.style, {
        display: 'flex',
        alignItems: 'center',
        padding: '12px 20px',
        borderRadius: '8px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
        opacity: '0',
        transform: 'translateY(20px)',
        transition: 'opacity 0.3s ease, transform 0.3s ease',
        // Disable the global .alert slideIn animation. Its
        // "both" fill-mode holds opacity:1 after the animation ends,
        // which overrides the inline styles and prevents the toast
        // from fading out. The toast already animates itself via the
        // transition above.
        animation: 'none'
    });

    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    });

    // Auto-dismiss after 4 seconds
    setTimeout(() => {
        if (!toast.isConnected) return;
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';

        let removed = false;
        const removeToast = () => {
            if (removed) return;
            removed = true;
            toast.remove();
        };
        toast.addEventListener('transitionend', removeToast);
        // Fallback in case transitionend never fires (e.g. reduced motion,
        // interrupted styles) so old toasts never get stuck.
        setTimeout(removeToast, 600);
    }, 4000);
}