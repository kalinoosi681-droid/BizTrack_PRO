// ========================================
// static/js/receiving.js
// Automated Pricing & Product Search for Receiving
// ========================================

const CURRENCY = 'M';

// Debounce helper
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}

// Fetch JSON helper
async function fetchJSON(url, options = {}) {
    try {
        const csrfToken = document.querySelector('input[name="csrf_token"]')?.value;
        const defaultHeaders = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };
        
        if (options.method === 'POST' && csrfToken) {
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

document.addEventListener('DOMContentLoaded', function() {
    // ========================================
    // PRODUCT SEARCH & SELECTION
    // ========================================
    const productSearch = document.getElementById('product-search');
    const productSuggest = document.getElementById('product-suggest');
    const productIdInput = document.getElementById('product-id');
    const productInfoCard = document.getElementById('product-info-card');
    
    let currentProduct = null;
    
    if (productSearch) {
        productSearch.addEventListener('input', debounce(async function(e) {
            const query = e.target.value.trim();
            
            if (!query) {
                productSuggest.classList.remove('show');
                productSuggest.innerHTML = '';
                return;
            }
            
            // Search products
            const products = await fetchJSON(`/api/search/products?q=${encodeURIComponent(query)}`);
            
            if (!products || products.length === 0) {
                productSuggest.innerHTML = '<div class="dropdown-item disabled">No products found</div>';
            } else {
                productSuggest.innerHTML = products.map(p => `
                    <button type="button" class="dropdown-item d-flex justify-content-between align-items-center" 
                            data-id="${p.id}">
                        <div>
                            <strong>${p.name}</strong>
                            <small class="text-muted d-block">${p.category} • Stock: ${p.qty}</small>
                        </div>
                        <span class="badge bg-secondary">#${p.id}</span>
                    </button>
                `).join('');
            }
            
            productSuggest.classList.add('show');
        }, 300));
        
        // Product selection
        productSuggest.addEventListener('click', async function(e) {
            const btn = e.target.closest('.dropdown-item');
            if (!btn || !btn.dataset.id) return;
            
            const productId = btn.dataset.id;
            
            // Load product details
            const product = await fetchJSON(`/receiving/api/product/${productId}`);
            
            if (product) {
                currentProduct = product;
                
                // Update form
                productIdInput.value = product.id;
                productSearch.value = product.name;
                
                // Show product info
                document.getElementById('product-name-display').textContent = product.name;
                document.getElementById('category-display').textContent = product.category;
                document.getElementById('current-stock-display').textContent = product.current_qty;
                productInfoCard.style.display = 'block';
                
                // Pre-fill cost price if available
                const costPriceInput = document.getElementById('cost-price');
                if (product.last_cost_price) {
                    costPriceInput.value = product.last_cost_price.toFixed(2);
                    costPriceInput.dispatchEvent(new Event('input'));
                }
                
                // Focus on quantity
                document.getElementById('quantity-received').focus();
            }
            
            productSuggest.classList.remove('show');
            productSuggest.innerHTML = '';
        });
        
        // Close dropdown on outside click
        document.addEventListener('click', function(e) {
            if (!productSearch.contains(e.target) && !productSuggest.contains(e.target)) {
                productSuggest.classList.remove('show');
            }
        });
    }
    
    // ========================================
    // AUTOMATED PRICE CALCULATION
    // ========================================
    const costPriceInput = document.getElementById('cost-price');
    const sellingPriceInput = document.getElementById('selling-price');
    const overrideCheckbox = document.getElementById('override-price');
    const marginDisplay = document.getElementById('margin-display');
    
    // Calculate selling price when cost price changes
    if (costPriceInput && sellingPriceInput) {
        costPriceInput.addEventListener('input', async function() {
            if (overrideCheckbox.checked || !currentProduct) return;
            
            const costPrice = parseFloat(this.value) || 0;
            
            if (costPrice > 0 && currentProduct) {
                const data = await fetchJSON('/receiving/api/calculate-price', {
                    method: 'POST',
                    body: JSON.stringify({
                        cost_price: costPrice,
                        category: currentProduct.category
                    })
                });
                
                if (data) {
                    sellingPriceInput.value = data.selling_price.toFixed(2);
                    marginDisplay.innerHTML = `
                        <i class="bi bi-check-circle text-success me-1"></i>
                        Auto: ${data.margin_percent}% margin (+${CURRENCY}${data.markup_amount})
                    `;
                    marginDisplay.classList.add('text-success');
                    marginDisplay.classList.remove('text-muted');
                    
                    // Update cost summary
                    updateCostSummary();
                }
            }
        });
        
        // Handle price override
        overrideCheckbox.addEventListener('change', function() {
            if (this.checked) {
                sellingPriceInput.readOnly = false;
                sellingPriceInput.classList.add('border-warning');
                marginDisplay.innerHTML = '<i class="bi bi-pencil-square text-warning me-1"></i>Manual override enabled';
                marginDisplay.classList.remove('text-success');
                marginDisplay.classList.add('text-warning');
            } else {
                sellingPriceInput.readOnly = true;
                sellingPriceInput.classList.remove('border-warning');
                costPriceInput.dispatchEvent(new Event('input')); // Recalculate
            }
        });
        
        // Manual price change
        sellingPriceInput.addEventListener('input', function() {
            if (overrideCheckbox.checked) {
                const costPrice = parseFloat(costPriceInput.value) || 0;
                const sellingPrice = parseFloat(this.value) || 0;
                
                if (costPrice > 0 && sellingPrice > 0) {
                    const margin = ((sellingPrice - costPrice) / costPrice * 100);
                    marginDisplay.innerHTML = `
                        <i class="bi bi-pencil-square text-warning me-1"></i>
                        Manual: ${margin.toFixed(1)}% margin (+${CURRENCY}${(sellingPrice - costPrice).toFixed(2)})
                    `;
                }
            }
            updateCostSummary();
        });
    }
    
    // ========================================
    // COST SUMMARY CALCULATION
    // ========================================
    const quantityInput = document.getElementById('quantity-received');
    const costSummary = document.getElementById('cost-summary');
    
    function updateCostSummary() {
        const quantity = parseFloat(quantityInput?.value) || 0;
        const costPrice = parseFloat(costPriceInput?.value) || 0;
        const sellingPrice = parseFloat(sellingPriceInput?.value) || 0;
        
        if (quantity > 0 && costPrice > 0 && sellingPrice > 0) {
            const totalCost = quantity * costPrice;
            const totalValue = quantity * sellingPrice;
            const profitMargin = ((sellingPrice - costPrice) / costPrice * 100);
            
            document.getElementById('total-cost-display').textContent = `${CURRENCY}${totalCost.toFixed(2)}`;
            document.getElementById('total-value-display').textContent = `${CURRENCY}${totalValue.toFixed(2)}`;
            document.getElementById('profit-margin-display').textContent = `${profitMargin.toFixed(1)}%`;
            
            costSummary.style.display = 'block';
        } else {
            costSummary.style.display = 'none';
        }
    }
    
    // Update summary on any input change
    [quantityInput, costPriceInput, sellingPriceInput].forEach(input => {
        if (input) {
            input.addEventListener('input', updateCostSummary);
        }
    });
    
    // ========================================
    // SUPPLIER AUTOCOMPLETE (OPTIONAL)
    // ========================================
    const supplierInput = document.getElementById('supplier-name');
    if (supplierInput) {
        // Could add supplier autocomplete here if needed
        // For now, just simple text input
    }
    
    // ========================================
    // FORM VALIDATION
    // ========================================
    const form = document.getElementById('receiving-form');
    const submitBtn = document.getElementById('submit-btn');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            // Check required fields
            if (!productIdInput.value) {
                e.preventDefault();
                alert('⚠️ Please select a product');
                productSearch.focus();
                return false;
            }
            
            const quantity = parseFloat(quantityInput.value) || 0;
            if (quantity <= 0) {
                e.preventDefault();
                alert('⚠️ Quantity must be greater than 0');
                quantityInput.focus();
                return false;
            }
            
            const costPrice = parseFloat(costPriceInput.value) || 0;
            if (costPrice <= 0) {
                e.preventDefault();
                alert('⚠️ Cost price must be greater than 0');
                costPriceInput.focus();
                return false;
            }
            
            const sellingPrice = parseFloat(sellingPriceInput.value) || 0;
            if (sellingPrice <= 0) {
                e.preventDefault();
                alert('⚠️ Selling price must be greater than 0');
                sellingPriceInput.focus();
                return false;
            }
            
            // Warn if selling price is less than cost price
            if (sellingPrice < costPrice) {
                if (!confirm(`⚠️ WARNING: Selling price (${CURRENCY}${sellingPrice}) is LESS than cost price (${CURRENCY}${costPrice}).\n\nYou will lose money on each sale!\n\nContinue anyway?`)) {
                    e.preventDefault();
                    return false;
                }
            }
            
            // Show loading state
            if (submitBtn) {
                const originalText = submitBtn.innerHTML;
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
                
                // Reset button after 5 seconds (in case form doesn't redirect)
                setTimeout(() => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }, 5000);
            }
        });
    }
    
    // ========================================
    // URL PARAMETER HANDLING
    // ========================================
    // Check if product_id is in URL (for quick receive from alerts)
    const urlParams = new URLSearchParams(window.location.search);
    const preloadProductId = urlParams.get('product_id');
    
    if (preloadProductId && productIdInput) {
        // Simulate product selection
        fetchJSON(`/receiving/api/product/${preloadProductId}`).then(product => {
            if (product) {
                currentProduct = product;
                productIdInput.value = product.id;
                productSearch.value = product.name;
                document.getElementById('product-name-display').textContent = product.name;
                document.getElementById('category-display').textContent = product.category;
                document.getElementById('current-stock-display').textContent = product.current_qty;
                productInfoCard.style.display = 'block';
                
                if (product.last_cost_price) {
                    costPriceInput.value = product.last_cost_price.toFixed(2);
                    costPriceInput.dispatchEvent(new Event('input'));
                }
                
                quantityInput.focus();
            }
        });
    }
    
    console.log('✅ Receiving system initialized successfully');
});