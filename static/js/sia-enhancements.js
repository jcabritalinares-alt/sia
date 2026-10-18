/**
 * SIA WEB - Optimizaciones de Experiencia de Usuario y Robustez
 * Módulos integrados:
 * 1. Indicador de Conectividad en Tiempo Real (Offline / Online)
 * 2. Protección Global contra Doble Envío (Double-Submit Protection)
 * 3. Formateo y Validación Predictiva de Teléfonos (Soporta 0412, 0414, 0424, 0416, 0426, 0422 y fijos 02XX)
 * 4. Normalización Automática de Cédulas
 * 5. Autoguardado Inteligente de Borradores en LocalStorage
 */

(function () {
    'use strict';

    // =========================================================================
    // 1. INDICADOR DE CONECTIVIDAD EN TIEMPO REAL (Offline / Online + Heartbeat)
    // =========================================================================
    function initConnectivityMonitor() {
        // 1.1 Contenedor Toast de Emergencia Flotante
        let toast = document.getElementById('sia-connectivity-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'sia-connectivity-toast';
            toast.innerHTML = `
                <i class="bi fs-5 toast-icon"></i>
                <div class="toast-content flex-grow-1"></div>
            `;
            document.body.appendChild(toast);
        }

        const iconEl = toast.querySelector('.toast-icon');
        const contentEl = toast.querySelector('.toast-content');
        let hideTimer = null;
        let isCurrentlyOnline = navigator.onLine;

        // 1.2 Obtener o crear badges de conectividad
        function getBadges() {
            let badges = Array.from(document.querySelectorAll('.badge-connectivity'));
            if (badges.length === 0) {
                // Crear badge flotante discreto si la página no tiene uno en su HTML
                const floatingBadge = document.createElement('div');
                floatingBadge.className = 'badge-connectivity d-inline-flex align-items-center gap-2 px-3 py-1.5 rounded-pill shadow-sm';
                floatingBadge.id = 'sia-floating-connectivity';
                floatingBadge.style.cssText = 'position: fixed; bottom: 18px; left: 18px; z-index: 9999; backdrop-filter: blur(8px);';
                floatingBadge.innerHTML = `
                    <span class="status-dot"></span>
                    <span class="status-text fw-semibold small">Verificando conexión...</span>
                `;
                document.body.appendChild(floatingBadge);
                badges.push(floatingBadge);
            }
            return badges;
        }

        function updateBadges(online, latencyMs = null, customMsg = null) {
            isCurrentlyOnline = online;
            const badges = getBadges();

            badges.forEach(badge => {
                badge.classList.remove('checking');
                const dot = badge.querySelector('.status-dot');
                const text = badge.querySelector('.status-text');

                if (online) {
                    badge.classList.remove('offline');
                    badge.title = latencyMs ? `Conectado a la base de datos (Latencia: ${latencyMs}ms). Clic para volver a probar.` : 'Conectado a internet. Clic para verificar.';
                    if (text) {
                        text.textContent = customMsg || (latencyMs ? `En línea (${latencyMs}ms)` : 'En línea');
                    }
                } else {
                    badge.classList.add('offline');
                    badge.title = 'Sin conexión al servidor. Clic para reintentar.';
                    if (text) {
                        text.textContent = customMsg || 'Sin conexión';
                    }
                }
            });
        }

        function showToast(online, customMsg = null) {
            clearTimeout(hideTimer);
            if (!online) {
                toast.className = 'offline show';
                iconEl.className = 'bi bi-wifi-off fs-4';
                contentEl.innerHTML = customMsg || '<strong>Sin conexión a internet.</strong> Los formularios que estés llenando se protegerán localmente.';
            } else {
                toast.className = 'online show';
                iconEl.className = 'bi bi-wifi fs-4';
                contentEl.innerHTML = customMsg || '<strong>Conexión restablecida.</strong> El sistema está sincronizado y en línea.';
                hideTimer = setTimeout(() => {
                    toast.classList.remove('show');
                }, 3500);
            }
        }

        // 1.3 Ping activo hacia /healthz/ para verificar conexión REAL
        async function checkConnectionActive(isManualClick = false) {
            const badges = getBadges();
            if (isManualClick) {
                badges.forEach(b => {
                    b.classList.add('checking');
                    const txt = b.querySelector('.status-text');
                    if (txt) txt.textContent = 'Probando...';
                });
            }

            const startTime = performance.now();
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 6000);

                const resp = await fetch('/healthz/', {
                    method: 'GET',
                    cache: 'no-store',
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                const latency = Math.round(performance.now() - startTime);

                if (resp.ok) {
                    const wasOffline = !isCurrentlyOnline;
                    updateBadges(true, latency);
                    if (wasOffline || isManualClick) {
                        showToast(true, `<strong>Conexión excelente.</strong> Servidor y base de datos respondiendo (${latency} ms).`);
                    }
                } else {
                    throw new Error(`HTTP ${resp.status}`);
                }
            } catch (err) {
                updateBadges(false);
                showToast(false, '<strong>No se puede contactar al servidor.</strong> Revisa tu conexión o espera un instante.');
            }
        }

        // 1.4 Eventos del navegador
        window.addEventListener('offline', () => {
            updateBadges(false);
            showToast(false);
        });

        window.addEventListener('online', () => {
            checkConnectionActive();
        });

        // 1.5 Click interactivo en cualquier badge de conectividad para probar bajo demanda
        document.addEventListener('click', function (e) {
            const badge = e.target.closest('.badge-connectivity');
            if (badge) {
                e.preventDefault();
                checkConnectionActive(true);
            }
        });

        // Verificación inicial inmediata y heartbeat cada 25 segundos
        checkConnectionActive();
        setInterval(checkConnectionActive, 25000);
    }

    // =========================================================================
    // 2. PROTECCIÓN GLOBAL CONTRA DOBLE ENVÍO (Double-Submit Protection)
    // =========================================================================
    function initDoubleSubmitProtection() {
        document.addEventListener('submit', function (e) {
            const form = e.target;
            if (!form || form.tagName !== 'FORM') return;

            // Evitar interceptar formularios de descarga o con target="_blank"
            if (form.getAttribute('target') === '_blank') return;

            // Si ya está enviándose, prevenir clics subsiguientes
            if (form.dataset.siaSubmitting === 'true') {
                e.preventDefault();
                return false;
            }

            // Marcar formulario como enviándose
            form.dataset.siaSubmitting = 'true';

            // Buscar el botón de envío
            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn) {
                submitBtn.classList.add('sia-btn-submitting');
                submitBtn.dataset.originalHtml = submitBtn.innerHTML;

                // Añadir spinner y texto indicador
                submitBtn.innerHTML = `
                    <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                    <span>Procesando...</span>
                `;
            }

            // Limpiar borrador de LocalStorage si el envío fue intencional
            clearFormDraft(form);

            // Timeout de seguridad de 15 segundos para reactivar por si la validación falla o se cancela
            setTimeout(() => {
                form.dataset.siaSubmitting = 'false';
                if (submitBtn && submitBtn.dataset.originalHtml) {
                    submitBtn.classList.remove('sia-btn-submitting');
                    submitBtn.innerHTML = submitBtn.dataset.originalHtml;
                }
            }, 15000);
        }, true);
    }

    // =========================================================================
    // 3. MÁSCARAS Y VALIDACIÓN PREDICTIVA DE TELÉFONOS (Incluye 0422) Y CÉDULAS
    // =========================================================================
    const PREFIJOS_MOVILES_VALIDOS = ['0412', '0414', '0424', '0416', '0426', '0422'];

    function formatearTelefono(val) {
        // Extraer solo dígitos
        const digits = val.replace(/\D/g, '');
        if (!digits) return '';

        // Si empieza por 58 (código de país), convertir a 0
        let cleaned = digits;
        if (cleaned.startsWith('58') && cleaned.length > 2) {
            cleaned = '0' + cleaned.substring(2);
        }

        // Limitar a máximo 11 dígitos estándar (4 de código + 7 de número)
        cleaned = cleaned.substring(0, 11);

        if (cleaned.length <= 4) {
            return cleaned;
        }
        return `${cleaned.substring(0, 4)}-${cleaned.substring(4)}`;
    }

    function validarPrefijoTelefono(val) {
        const digits = val.replace(/\D/g, '');
        if (digits.length < 4) return { valid: true, msg: '' };

        const prefijo = digits.substring(0, 4);
        const esMovil = prefijo.startsWith('04');
        const esFijo = prefijo.startsWith('02');

        if (esMovil) {
            if (PREFIJOS_MOVILES_VALIDOS.includes(prefijo)) {
                return { valid: true, msg: 'Prefijo móvil verificado.' };
            } else {
                return {
                    valid: false,
                    msg: `Prefijo no reconocido. Prefijos válidos: ${PREFIJOS_MOVILES_VALIDOS.join(', ')}`
                };
            }
        } else if (esFijo) {
            return { valid: true, msg: 'Prefijo fijo nacional verificado.' };
        } else {
            return {
                valid: false,
                msg: `El número debe comenzar con un prefijo nacional (ej: 0412, 0414, 0424, 0416, 0426, 0422 o fijo 02XX).`
            };
        }
    }

    function attachPhoneMask(input) {
        if (!input) return;
        // Jamás aplicar máscara de teléfono a inputs de cédula
        const inputId = (input.id || '').toLowerCase();
        const inputName = (input.name || '').toLowerCase();
        if (inputId.includes('cedula') || inputName.includes('cedula')) {
            return;
        }
        if (input.dataset.siaPhoneMaskAttached === 'true') return;
        input.dataset.siaPhoneMaskAttached = 'true';

        // Contenedor de feedback
        let feedback = input.parentElement.querySelector('.sia-phone-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            feedback.className = 'sia-phone-feedback';
            input.parentElement.appendChild(feedback);
        }

        function handleInput() {
            const rawVal = input.value;
            const formatted = formatearTelefono(rawVal);
            if (rawVal !== formatted) {
                input.value = formatted;
            }

            const check = validarPrefijoTelefono(input.value);
            if (input.value.trim().length >= 4) {
                feedback.classList.add('show');
                if (check.valid) {
                    feedback.className = 'sia-phone-feedback show valid';
                    feedback.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i> ${check.msg}`;
                } else {
                    feedback.className = 'sia-phone-feedback show invalid';
                    feedback.innerHTML = `<i class="bi bi-exclamation-circle-fill me-1"></i> ${check.msg}`;
                }
            } else {
                feedback.classList.remove('show');
            }
        }

        input.addEventListener('input', handleInput);
        input.addEventListener('blur', handleInput);

        // Formatear si ya trae valor
        if (input.value) {
            handleInput();
        }
    }

    function attachCedulaMask(input) {
        if (input.dataset.siaCedulaMaskAttached === 'true') return;
        input.dataset.siaCedulaMaskAttached = 'true';

        function sanitizeCedula(raw) {
            let val = raw.trim().toUpperCase();
            // Soporte automático para escaneo de Carnet QR (SIA:CEDULA:V-12345678)
            if (val.includes('SIA:CEDULA:')) {
                val = val.replace('SIA:CEDULA:', '').trim();
            }
            return val.replace(/[^VvEeJjGg0-9\-]/g, '');
        }

        input.addEventListener('input', function () {
            input.value = sanitizeCedula(input.value);
        });

        input.addEventListener('paste', function () {
            setTimeout(() => {
                input.value = sanitizeCedula(input.value);
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }, 10);
        });
    }

    function initInputMasks() {
        // Encontrar todos los inputs de teléfono (excluyendo cédula)
        const phoneInputs = document.querySelectorAll('input[type="tel"]:not([id*="cedula"]):not([name*="cedula"]), input[name*="telefono"], input[id*="telefono"]');
        phoneInputs.forEach(attachPhoneMask);

        // Encontrar todos los inputs de cédula
        const cedulaInputs = document.querySelectorAll('input[name*="cedula"], input[id*="cedula"]');
        cedulaInputs.forEach(attachCedulaMask);
    }

    // =========================================================================
    // 4. AUTOGUARDADO INTELIGENTE DE BORRADORES EN LOCALSTORAGE
    // =========================================================================
    function getFormStorageKey(form) {
        const idOrAction = form.id || form.getAttribute('action') || window.location.pathname;
        return `sia_draft_${window.location.pathname}_${idOrAction}`;
    }

    function saveFormDraft(form) {
        try {
            const data = {};
            const elements = form.elements;
            let hasContent = false;

            for (let i = 0; i < elements.length; i++) {
                const el = elements[i];
                if (!el.name || el.type === 'password' || el.type === 'file' || el.type === 'hidden') continue;
                if (el.name === 'csrfmiddlewaretoken') continue;

                if (el.type === 'checkbox' || el.type === 'radio') {
                    if (el.checked) {
                        data[el.name] = el.value;
                        hasContent = true;
                    }
                } else if (el.value && el.value.trim().length > 0) {
                    data[el.name] = el.value;
                    hasContent = true;
                }
            }

            const storageKey = getFormStorageKey(form);
            if (hasContent) {
                localStorage.setItem(storageKey, JSON.stringify({
                    timestamp: Date.now(),
                    fields: data
                }));
            }
        } catch (e) {
            console.warn('SIA Autosave: No se pudo guardar borrador', e);
        }
    }

    function clearFormDraft(form) {
        try {
            const storageKey = getFormStorageKey(form);
            localStorage.removeItem(storageKey);
        } catch (e) {}
    }

    function restoreFormDraft(form, draftData) {
        if (!draftData || !draftData.fields) return;

        Object.keys(draftData.fields).forEach(name => {
            const field = form.elements[name];
            if (field) {
                if (field.type === 'checkbox' || field.type === 'radio') {
                    field.checked = (field.value === draftData.fields[name]);
                } else {
                    field.value = draftData.fields[name];
                }
                // Disparar eventos para actualizar máscaras y autocompletados
                field.dispatchEvent(new Event('input', { bubbles: true }));
                field.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    }

    function initFormAutosave() {
        // Formularios elegibles para autoguardado (entregas, atención al ciudadano, asignaciones especiales)
        const targetForms = document.querySelectorAll(
            '#formRegistro, #form-solicitud, form[action*="entregar"], form[action*="atencion-ciudadano"], form[action*="asignaciones-especiales"], .sia-autosave'
        );

        targetForms.forEach(form => {
            const storageKey = getFormStorageKey(form);
            const savedDraftRaw = localStorage.getItem(storageKey);

            if (savedDraftRaw) {
                try {
                    const savedDraft = JSON.parse(savedDraftRaw);
                    // Validar que el borrador no tenga más de 48 horas
                    const isRecent = (Date.now() - savedDraft.timestamp) < (48 * 3600 * 1000);

                    // Verificar si el formulario está vacío actualmente
                    const cedulaInput = form.querySelector('input[name*="cedula"]');
                    const isFormEmpty = !cedulaInput || !cedulaInput.value.trim();

                    if (isRecent && isFormEmpty && savedDraft.fields && Object.keys(savedDraft.fields).length > 0) {
                        const alertBox = document.createElement('div');
                        alertBox.className = 'sia-draft-alert';
                        alertBox.innerHTML = `
                            <div class="draft-text">
                                <i class="bi bi-clock-history fs-5 text-primary"></i>
                                <span>Hay un borrador sin guardar en este equipo. ¿Deseas restaurar la información?</span>
                            </div>
                            <div class="draft-actions">
                                <button type="button" class="btn btn-sm btn-primary rounded-pill px-3 btn-restore">
                                    <i class="bi bi-arrow-counterclockwise me-1"></i> Restaurar
                                </button>
                                <button type="button" class="btn btn-sm btn-outline-secondary rounded-pill px-3 btn-discard">
                                    Descartar
                                </button>
                            </div>
                        `;

                        form.insertBefore(alertBox, form.firstChild);

                        alertBox.querySelector('.btn-restore').addEventListener('click', () => {
                            restoreFormDraft(form, savedDraft);
                            alertBox.remove();
                            // Notificación de éxito
                            const toast = document.getElementById('sia-connectivity-toast');
                            if (toast) {
                                toast.className = 'online show';
                                toast.querySelector('.toast-icon').className = 'bi bi-check-circle-fill fs-4';
                                toast.querySelector('.toast-content').innerHTML = '<strong>Borrador restaurado con éxito.</strong>';
                                setTimeout(() => toast.classList.remove('show'), 3000);
                            }
                        });

                        alertBox.querySelector('.btn-discard').addEventListener('click', () => {
                            clearFormDraft(form);
                            alertBox.remove();
                        });
                    }
                } catch (e) {
                    clearFormDraft(form);
                }
            }

            // Escuchar cambios para autoguardar con debounce
            let saveTimeout = null;
            form.addEventListener('input', () => {
                clearTimeout(saveTimeout);
                saveTimeout = setTimeout(() => saveFormDraft(form), 600);
            });
            form.addEventListener('change', () => {
                clearTimeout(saveTimeout);
                saveTimeout = setTimeout(() => saveFormDraft(form), 600);
            });
        });
    }

    // =========================================================================
    // INICIALIZACIÓN AL CARGAR EL DOM
    // =========================================================================
    document.addEventListener('DOMContentLoaded', function () {
        initConnectivityMonitor();
        initDoubleSubmitProtection();
        initInputMasks();
        initFormAutosave();

        // Re-evaluar máscaras si se insertan campos dinámicamente
        const observer = new MutationObserver(() => {
            initInputMasks();
        });
        observer.observe(document.body, { childList: true, subtree: true });
    });

})();
