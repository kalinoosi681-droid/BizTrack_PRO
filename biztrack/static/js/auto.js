// ========================================
// Enhanced Autocomplete & Search with Maloti Currency - auto.js
// ========================================

// Currency Configuration
const CURRENCY = 'M'; // Lesotho Maloti

// ========================================
// GLOBAL UTILITIES
// ========================================

const debounce = (fn, wait = 300) => {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn(...args), wait);
    };
};

async function fetchJSON(url, options = {}) {
    try {
        const csrfToken = document.querySelector('input[name="csrf_token"]')?.value;
        const defaultHeaders = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };
        
        if (options.method && options.method.toUpperCase() === 'POST' && csrfToken) {
            defaultHeaders['X-CSRFToken'] = csrfToken;
        }
        
        const response = await fetch(url, {
            ...options,
            headers: { ...defaultHeaders, ...options.headers }
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error(`Fetch error on ${url}:`, error);
        return null;
    }
}

// ========================================
// GLOBAL SEARCH
// ========================================
(() => {
    const gInput = document.getElementById('global_search');
    const gMenu = document.getElementById('global_results');
    
    if (!gInput || !gMenu) return;

    gInput.addEventListener('input', debounce(async (e) => {
        const q = e.target.value.trim();
        
        if (!q) {
            gMenu.innerHTML = '';
            return;
        }

        gMenu.innerHTML = '<div class="list-group-item"><i class="fas fa-spinner fa-spin me-2"></i>Searching...</div>';
        
        const data = await fetchJSON(`/api/search?q=${encodeURIComponent(q)}`);
        
        if (!data) {
            gMenu.innerHTML = '<div class="list-group-item text-danger"><i class="fas fa-exclamation-triangle me-2"></i>Search failed</div>';
            return;
        }

        const rows = [];
        
        (data.products || []).forEach(p => {
            rows.push(`
                <a class="list-group-item list-group-item-action d-flex justify-content-between align-items-center" href="${p.url}">
                    <div class="flex-grow-1 me-2" style="min-width: 0;">
                        <i class="fas fa-box text-primary me-2"></i>
                        <strong>${p.name}</strong>
                        <small class="text-muted d-block">${p.category} • ${CURRENCY}${p.price.toFixed(2)}</small>
                    </div>
                    <span class="badge bg-primary">#${p.id}</span>
                </a>
            `);
        });
        
        (data.customers || []).forEach(c => {
            rows.push(`
                <a class="list-group-item list-group-item-action d-flex justify-content-between align-items-center" href="${c.url}">
                    <div class="flex-grow-1 me-2" style="min-width: 0;">
                        <i class="fas fa-user text-success me-2"></i>
                        <strong>${c.name}</strong>
                        <small class="text-muted d-block">${c.phone || 'No phone'}</small>
                    </div>
                    <span class="badge bg-success">#${c.id}</span>
                </a>
            `);
        });
        
        (data.invoices || []).forEach(i => {
            rows.push(`
                <a class="list-group-item list-group-item-action d-flex justify-content-between align-items-center" href="${i.url}">
                    <div class="flex-grow-1 me-2" style="min-width: 0;">
                        <i class="fas fa-file-invoice text-warning me-2"></i>
                        <strong>Invoice #${i.id}</strong>
                        <small class="text-muted d-block">${CURRENCY}${i.total.toFixed(2)} • ${i.date}</small>
                    </div>
                    <span class="badge bg-warning text-dark">#${i.id}</span>
                </a>
            `);
        });
        
        if (rows.length === 0) {
            gMenu.innerHTML = '<div class="list-group-item text-muted"><i class="fas fa-search me-2"></i>No results found</div>';
        } else {
            gMenu.innerHTML = rows.join('');
        }
    }, 300));

    document.addEventListener('click', (e) => {
        if (!gInput.contains(e.target) && !gMenu.contains(e.target)) {
            gMenu.innerHTML = '';
        }
    });
})();

// ========================================
// CUSTOMERS: Add/Update Autocomplete
// ========================================
(() => {
    const cInput = document.getElementById('customer_search');
    const cMenu = document.getElementById('customer_suggest');
    
    if (!cInput || !cMenu) return;

    cInput.addEventListener('input', debounce(async (e) => {
        const q = e.target.value.trim();
        
        if (!q) {
            cMenu.classList.remove('show');
            cMenu.innerHTML = '';
            return;
        }

        const items = await fetchJSON(`/api/search/customers?q=${encodeURIComponent(q)}`);
        
        if (!items || items.length === 0) {
            cMenu.innerHTML = '<button class="dropdown-item disabled">No customers found</button>';
        } else {
            cMenu.innerHTML = items.map(i => `
                <button type="button" class="dropdown-item d-flex justify-content-between align-items-center" data-json='${JSON.stringify(i)}'>
                    <div>
                        <strong>${i.name}</strong>
                        <small class="text-muted d-block">${i.phone || 'No phone'} • ${CURRENCY}${i.total_spend.toFixed(2)} total</small>
                    </div>
                    <span class="badge bg-secondary">#${i.id}</span>
                </button>
            `).join('');
        }
        
        cMenu.classList.add('show');
    }));

    cMenu.addEventListener('click', (e) => {
        const btn = e.target.closest('.dropdown-item');
        if (!btn || !btn.dataset.json) return;
        
        const i = JSON.parse(btn.dataset.json);
        
        const updFields = [
            ['#update_customer_id', 'id'],
            ['#update_customer_name', 'name'],
            ['#update_customer_phone', 'phone'],
            ['#update_customer_email', 'email']
        ];
        
        updFields.forEach(([sel, key]) => {
            const el = document.querySelector(sel);
            if (el) el.value = i[key] || '';
        });

        cInput.value = i.name;
        cMenu.classList.remove('show');
    });

    document.addEventListener('click', (e) => {
        if (!cInput.contains(e.target) && !cMenu.contains(e.target)) {
            cMenu.classList.remove('show');
        }
    });
})();

// ========================================
// PRODUCTS: Add/Update Autocomplete (FIXED)
// ========================================
(() => {
    const pInput = document.getElementById('product_search');
    const pMenu = document.getElementById('product_suggest');
    
    if (!pInput || !pMenu) return;

    pInput.addEventListener('input', debounce(async (e) => {
        const q = e.target.value.trim();
        
        if (!q) {
            pMenu.classList.remove('show');
            pMenu.innerHTML = '';
            return;
        }

        const items = await fetchJSON(`/api/search/products?q=${encodeURIComponent(q)}`);
        
        if (!items || items.length === 0) {
            pMenu.innerHTML = '<button class="dropdown-item disabled">No products found</button>';
        } else {
            pMenu.innerHTML = items.map(i => {
                let statusBadge = '';
                if (i.flag === 'fast') {
                    statusBadge = '<span class="badge bg-success ms-2">🔥 Fast</span>';
                } else if (i.flag === 'slow') {
                    statusBadge = '<span class="badge bg-warning text-dark ms-2">🐢 Slow</span>';
                }
                
                return `
                    <button type="button" class="dropdown-item d-flex justify-content-between align-items-center" data-json='${JSON.stringify(i)}'>
                        <div>
                            <strong>${i.name}</strong>
                            <small class="text-muted d-block">${i.category} • ${CURRENCY}${i.price.toFixed(2)} • ${i.qty} in stock</small>
                        </div>
                        <div>
                            <span class="badge bg-secondary">#${i.id}</span>
                            ${statusBadge}
                        </div>
                    </button>
                `;
            }).join('');
        }
        
        pMenu.classList.add('show');
    }));

    pMenu.addEventListener('click', (e) => {
        const btn = e.target.closest('.dropdown-item');
        if (!btn || !btn.dataset.json) return;
        
        const i = JSON.parse(btn.dataset.json);
        
        // FIXED: Populate update form fields
        const updFields = [
            ['#update_product_id', 'id'],
            ['#update_product_name', 'name'],
            ['#update_product_category', 'category'],
            ['#update_product_qty', 'qty'],
            ['#update_product_price', 'price']
        ];
        
        updFields.forEach(([sel, key]) => {
            const el = document.querySelector(sel);
            if (el) el.value = i[key] || '';
        });

        pInput.value = i.name;
        pMenu.classList.remove('show');
        
        // Scroll to form
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    document.addEventListener('click', (e) => {
        if (!pInput.contains(e.target) && !pMenu.contains(e.target)) {
            pMenu.classList.remove('show');
        }
    });
})();

// ========================================
// INVOICES: Customer Search
// ========================================
(() => {
    const invCInput = document.getElementById('inv_customer_search');
    const invCMenu = document.getElementById('inv_customer_suggest');
    
    if (!invCInput || !invCMenu) return;

    invCInput.addEventListener('input', debounce(async (e) => {
        const q = e.target.value.trim();
        
        if (!q) {
            invCMenu.classList.remove('show');
            invCMenu.innerHTML = '';
            return;
        }

        const items = await fetchJSON(`/api/search/customers?q=${encodeURIComponent(q)}`);
        
        if (!items || items.length === 0) {
            invCMenu.innerHTML = '<button class="dropdown-item disabled">No customers found</button>';
        } else {
            invCMenu.innerHTML = items.map(i => `
                <button type="button" class="dropdown-item d-flex justify-content-between align-items-center" data-json='${JSON.stringify(i)}'>
                    <div>
                        <strong>${i.name}</strong>
                        <small class="text-muted d-block">${i.phone || 'No phone'}</small>
                    </div>
                    <span class="badge bg-secondary">#${i.id}</span>
                </button>
            `).join('');
        }
        
        invCMenu.classList.add('show');
    }));

    invCMenu.addEventListener('click', (e) => {
        const btn = e.target.closest('.dropdown-item');
        if (!btn || !btn.dataset.json) return;
        
        const i = JSON.parse(btn.dataset.json);
        const cidEl = document.getElementById('inv_customer_id');
        
        if (cidEl) cidEl.value = i.id;
        invCInput.value = i.name;
        invCMenu.classList.remove('show');
    });

    document.addEventListener('click', (e) => {
        if (!invCInput.contains(e.target) && !invCMenu.contains(e.target)) {
            invCMenu.classList.remove('show');
        }
    });
})();

// ========================================
// INVOICES: DYNAMIC LINE ITEMS
// ========================================
(() => {
    const invoiceForm = document.getElementById('invoiceForm');
    if (!invoiceForm) return;

    let itemIndex = 1;

    document.getElementById('addItemBtn')?.addEventListener('click', function() {
        const container = document.getElementById('itemsContainer');
        const newRow = `
            <div class="row mb-3 pb-3 border-bottom item-row" data-item-index="${itemIndex}">
                <div class="col-md-5">
                    <label class="form-label"><i class="fas fa-box me-1"></i>Product</label>
                    <div class="position-relative">
                        <input type="text" class="form-control product_search" placeholder="Search product..." autocomplete="off" required>
                        <div class="dropdown-menu w-100 product_suggest" style="max-height: 250px; overflow-y: auto; z-index: 1051;"></div>
                    </div>
                    <input type="number" name="items-${itemIndex}-pid" class="form-control mt-2" placeholder="Product ID" readonly required>
                </div>
                <div class="col-md-3">
                    <label class="form-label"><i class="fas fa-shopping-cart me-1"></i>Quantity</label>
                    <input type="number" name="items-${itemIndex}-qty" class="form-control qty-input" placeholder="Qty" min="1" required>
                </div>
                <div class="col-md-3">
                    <label class="form-label"><i class="fas fa-coins me-1"></i>Price (${CURRENCY})</label>
                    <input type="number" name="items-${itemIndex}-price" class="form-control price-input" step="0.01" placeholder="0.00" readonly required>
                </div>
                <div class="col-md-1 d-flex align-items-end">
                    <button type="button" class="btn btn-danger btn-sm remove-item" title="Remove item"><i class="fas fa-trash"></i></button>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', newRow);
        itemIndex++;
    });

    document.addEventListener('click', function(e) {
        if (e.target.closest('.remove-item')) {
            const rows = document.querySelectorAll('.item-row');
            if (rows.length > 1) {
                e.target.closest('.item-row').remove();
                updateTotal();
            } else {
                alert('You must have at least one item!');
            }
        }
    });

    function updateTotal() {
        let total = 0;
        document.querySelectorAll('.item-row').forEach(row => {
            const qty = parseFloat(row.querySelector('.qty-input')?.value) || 0;
            const price = parseFloat(row.querySelector('.price-input')?.value) || 0;
            total += qty * price;
        });
        const totalEl = document.getElementById('totalPreview');
        if (totalEl) totalEl.textContent = `${CURRENCY}${total.toFixed(2)}`;
    }

    document.addEventListener('input', function(e) {
        if (e.target.classList.contains('qty-input') || e.target.classList.contains('price-input')) {
            updateTotal();
        }
    });

    document.addEventListener('input', debounce(async function(e) {
        if (!e.target.classList.contains('product_search')) return;

        const input = e.target;
        const menu = input.nextElementSibling;
        const q = input.value.trim();

        if (!q) {
            menu.classList.remove('show');
            menu.innerHTML = '';
            return;
        }

        const items = await fetchJSON(`/api/search/products?q=${encodeURIComponent(q)}`);
        if (!items || items.length === 0) {
            menu.innerHTML = '<button class="dropdown-item disabled">No products found</button>';
        } else {
            menu.innerHTML = items.map(i => `
                <button type="button" class="dropdown-item d-flex justify-content-between align-items-center" data-json='${JSON.stringify(i)}'>
                    <div><strong>${i.name}</strong><small class="text-muted d-block">${CURRENCY}${i.price.toFixed(2)} • ${i.qty} available</small></div>
                    <span class="badge bg-secondary">#${i.id}</span>
                </button>
            `).join('');
        }
        menu.classList.add('show');
    }, 300));

    document.addEventListener('click', function(e) {
        if (e.target.closest('.product_suggest .dropdown-item')) {
            const btn = e.target.closest('.dropdown-item');
            if (!btn.dataset.json) return;

            const i = JSON.parse(btn.dataset.json);
            const row = btn.closest('.item-row');
            
            row.querySelector('[name*="pid"]').value = i.id;
            row.querySelector('[name*="price"]').value = i.price.toFixed(2);
            row.querySelector('.product_search').value = i.name;
            btn.parentElement.classList.remove('show');
            updateTotal();
        }
    });
})();

// ========================================
// AI-POWERED PRODUCT CREATION
// ========================================
(() => {
    const addForm = document.getElementById('product_add_form');
    if (!addForm) return;

    const nameInput = addForm.querySelector('#add_product_name');
    const categoryInput = addForm.querySelector('#add_product_category');
    const priceInput = addForm.querySelector('#add_product_price');
    const qtyInput = addForm.querySelector('#add_product_qty');
    const suggestionBox = document.getElementById('ai_product_suggestions');

    if (!nameInput || !suggestionBox) return;
    
    nameInput.addEventListener('input', debounce(async (e) => {
        const productName = e.target.value.trim();
        const userCategory = categoryInput?.value.trim();
        
        if (productName.length < 4) {
            suggestionBox.style.display = 'none';
            suggestionBox.innerHTML = '';
            return;
        }
    
        suggestionBox.style.display = 'block';
        suggestionBox.innerHTML = '<div class="text-muted"><i class="fas fa-robot fa-spin me-2"></i>AI analyzing Lesotho market data...</div>';

        const data = await fetchJSON('/api/ai/predict-product', {
            method: 'POST',
            body: JSON.stringify({ product_name: productName, category: userCategory })
        });

        if (data && data.category && data.price && data.stock) {
            if (categoryInput) categoryInput.value = data.category.predicted;
            if (priceInput) priceInput.value = data.price.suggested_price;
            if (qtyInput) qtyInput.value = data.stock.recommended_qty;

            suggestionBox.innerHTML = `
                <div class="alert alert-success small p-3" style="animation: fadeIn 0.3s ease-out;">
                    <i class="fas fa-check-circle me-2"></i>
                    <strong>🇱🇸 AI Suggestions Applied (Lesotho Market)</strong>
                    <ul class="list-unstyled mb-0 mt-2 small">
                        <li>
                            <strong>Category:</strong> ${data.category.predicted} 
                            <span class="badge bg-success">${data.category.confidence}% confidence</span>
                        </li>
                        <li>
                            <strong>Price:</strong> ${CURRENCY}${data.price.suggested_price} 
                            <small class="text-muted">(${data.price.reasoning})</small>
                        </li>
                        ${data.price.market_avg ? `<li><strong>Market Avg:</strong> ${CURRENCY}${data.price.market_avg} (incl. 15% VAT)</li>` : ''}
                        <li><strong>Stock:</strong> ${data.stock.recommended_qty} units</li>
                        ${data.similar_products && data.similar_products.length > 0 ? `
                            <li class="mt-2">
                                <small class="text-muted">
                                    <i class="fas fa-link me-1"></i>Similar: 
                                    ${data.similar_products.map(p => p.name).join(', ')}
                                </small>
                            </li>
                        ` : ''}
                    </ul>
                </div>`;
        } else {
            suggestionBox.innerHTML = '<div class="text-muted small">AI suggestion unavailable. Using defaults.</div>';
        }
    }, 800));
})();

// ========================================
// ENHANCED LOADING STATES
// ========================================
(() => {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"], input[type="submit"]');
            
            if (submitBtn && !submitBtn.disabled) {
                const originalText = submitBtn.innerHTML;
                submitBtn.dataset.originalText = originalText;
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
            }
        });
    });
    
    window.addEventListener('pageshow', () => {
        document.querySelectorAll('button[type="submit"][disabled], input[type="submit"][disabled]').forEach(submitBtn => {
            if (submitBtn.dataset.originalText) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = submitBtn.dataset.originalText;
            }
        });
    });
})();

// ========================================
// TOOLTIPS & POPOVERS
// ========================================
(() => {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    [...popoverTriggerList].map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
})();

// ========================================
// THEME TOGGLE
// ========================================
(() => {
    const lightBtn = document.getElementById('theme-light-btn');
    const darkBtn = document.getElementById('theme-dark-btn');
    const htmlEl = document.documentElement;

    if (!lightBtn || !darkBtn) return;

    const setTheme = (theme) => {
        htmlEl.setAttribute('data-bs-theme', theme);
        localStorage.setItem('theme', theme);
        updateActiveButton(theme);
    };

    const updateActiveButton = (theme) => {
        if (theme === 'light') {
            lightBtn.classList.add('active');
            darkBtn.classList.remove('active');
        } else {
            darkBtn.classList.add('active');
            lightBtn.classList.remove('active');
        }
    };

    lightBtn.addEventListener('click', () => setTheme('light'));
    darkBtn.addEventListener('click', () => setTheme('dark'));

    updateActiveButton(localStorage.getItem('theme') || 'dark');
})();

console.log('✅ BizTrack PRO - Enhanced with Lesotho Market Intelligence initialized');