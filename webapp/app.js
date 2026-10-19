const { createApp } = Vue;

const FALLBACK_IMAGE_SVG = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300" fill="none"><rect width="300" height="300" fill="%23F1F5F9"/><rect x="80" y="60" width="140" height="180" rx="16" fill="%23003865" fill-opacity="0.1" stroke="%23003865" stroke-width="3" stroke-dasharray="6 6"/><circle cx="150" cy="140" r="28" fill="%23009FDA" fill-opacity="0.2"/><path d="M140 140H160M150 130V150" stroke="%23009FDA" stroke-width="3" stroke-linecap="round"/><text x="150" y="210" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="bold" fill="%23003865">TORK</text></svg>`;

createApp({
  data() {
    return {
      products: [],
      loading: true,
      error: null,
      selectedZone: 'zone_wash',
      selectedCategory: 'all', // 'all' | 'dispenser' | 'refill'
      searchQuery: '',
      cart: {}, // { [sku]: { ...product, qty: number } }
      isCartOpen: false,
      preselectedSku: null,
      orderSuccess: false,
      isSubmitting: false,
      submittedOrderData: null,
      copiedPayload: false,
      form: {
        company_name: '',
        bin: '',
        city: 'Алматы',
        client_name: '',
        phone: '+7'
      },
      formErrors: {},
      zones: [
        { id: 'zone_wash', label: 'Мытье рук', icon: '🧼' },
        { id: 'zone_toilet', label: 'Туалетная зона', icon: '🚽' },
        { id: 'zone_accessories', label: 'Оснащение', icon: '🗑' },
        { id: 'zone_wiping', label: 'Протирка', icon: '🧻' }
      ],
      cities: ['Астана', 'Алматы', 'Шымкент']
    };
  },

  computed: {
    cartItems() {
      return Object.values(this.cart);
    },

    cartTotalQty() {
      return this.cartItems.reduce((sum, item) => sum + item.qty, 0);
    },

    cartTotalAmount() {
      return this.cartItems.reduce((sum, item) => sum + item.price * item.qty, 0);
    },

    currentZoneProducts() {
      return this.products.filter(p => p.zone === this.selectedZone);
    },

    zoneCounts() {
      const counts = { all: 0, dispenser: 0, refill: 0 };
      const current = this.currentZoneProducts;
      counts.all = current.length;
      for (const p of current) {
        if (p.category === 'dispenser') counts.dispenser++;
        if (p.category === 'refill') counts.refill++;
      }
      return counts;
    },

    filteredProducts() {
      const q = this.searchQuery.trim().toLowerCase();
      if (q.length > 0) {
        return this.products.filter(p => 
          p.sku.toLowerCase().includes(q) || 
          p.name.toLowerCase().includes(q) ||
          p.system_code.toLowerCase().includes(q)
        );
      }

      return this.currentZoneProducts.filter(p => {
        if (this.selectedCategory === 'all') return true;
        return p.category === this.selectedCategory;
      });
    }
  },

  mounted() {
    this.initTelegram();
    this.loadCatalog();
  },

  methods: {
    initTelegram() {
      if (window.Telegram && window.Telegram.WebApp) {
        const tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();
        if (tg.setHeaderColor) {
          tg.setHeaderColor('#003865');
        }
        if (tg.setBackgroundColor) {
          tg.setBackgroundColor('#F8FAFC');
        }
      }
    },

    async loadCatalog() {
      this.loading = true;
      this.error = null;
      try {
        // Try relative first, then fallback to /app/products.json
        let res;
        try {
          res = await fetch('products.json');
          if (!res.ok) throw new Error('Not found relative');
        } catch (e) {
          res = await fetch('/app/products.json');
        }

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: Failed to load catalog data`);
        }

        const data = await res.json();
        this.products = data;
        this.loading = false;

        this.handlePreselectedSku();
      } catch (err) {
        console.error('Catalog load error:', err);
        this.error = 'Не удалось загрузить каталог товаров. Проверьте соединение с сервером.';
        this.loading = false;
      }
    },

    handlePreselectedSku() {
      const urlParams = new URLSearchParams(window.location.search);
      const preselect = urlParams.get('preselect_sku');
      if (preselect) {
        this.preselectedSku = String(preselect).trim();
        const item = this.products.find(p => p.sku === this.preselectedSku);
        if (item) {
          this.selectedZone = item.zone;
          this.addToCart(item, 1);
          this.$nextTick(() => {
            const el = document.getElementById(`product-${this.preselectedSku}`);
            if (el) {
              el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          });
        }
      }
    },

    formatPrice(val) {
      if (!val && val !== 0) return '0 ₸';
      return Math.round(val).toLocaleString('ru-RU') + ' ₸';
    },

    selectZone(zoneId) {
      this.selectedZone = zoneId;
      this.searchQuery = '';
      this.haptic('selection');
    },

    selectCategory(cat) {
      this.selectedCategory = cat;
      this.haptic('selection');
    },

    clearSearch() {
      this.searchQuery = '';
    },

    addToCart(product, qty = 1) {
      if (!this.cart[product.sku]) {
        this.cart = {
          ...this.cart,
          [product.sku]: {
            sku: product.sku,
            name: product.name,
            price: product.price,
            system_code: product.system_code,
            category: product.category,
            color: product.color,
            image_url: product.image_url,
            qty: qty
          }
        };
      } else {
        this.cart[product.sku].qty += qty;
      }
      this.haptic('impact');
    },

    updateQty(sku, delta) {
      if (!this.cart[sku]) return;
      const newQty = this.cart[sku].qty + delta;
      if (newQty <= 0) {
        const nextCart = { ...this.cart };
        delete nextCart[sku];
        this.cart = nextCart;
      } else {
        this.cart[sku].qty = newQty;
      }
      this.haptic('impact');
    },

    removeFromCart(sku) {
      if (this.cart[sku]) {
        const nextCart = { ...this.cart };
        delete nextCart[sku];
        this.cart = nextCart;
        this.haptic('notification');
      }
    },

    getItemQty(sku) {
      return this.cart[sku]?.qty || 0;
    },

    openCart() {
      this.isCartOpen = true;
      this.formErrors = {};
      this.haptic('impact');
    },

    closeCart() {
      this.isCartOpen = false;
      this.orderSuccess = false;
    },

    onBinInput(e) {
      const digitsOnly = e.target.value.replace(/\D/g, '').slice(0, 12);
      this.form.bin = digitsOnly;
      if (this.formErrors.bin && digitsOnly.length === 12) {
        delete this.formErrors.bin;
      }
    },

    onPhoneInput(e) {
      let raw = e.target.value.replace(/\D/g, '');
      if (raw.startsWith('8')) {
        raw = '7' + raw.slice(1);
      }
      if (!raw.startsWith('7')) {
        raw = '7' + raw;
      }
      raw = raw.slice(0, 11);

      let formatted = '+7';
      if (raw.length > 1) {
        formatted += ' (' + raw.slice(1, 4);
      }
      if (raw.length >= 4) {
        formatted += ') ' + raw.slice(4, 7);
      }
      if (raw.length >= 7) {
        formatted += '-' + raw.slice(7, 9);
      }
      if (raw.length >= 9) {
        formatted += '-' + raw.slice(9, 11);
      }

      this.form.phone = formatted;
      if (this.formErrors.phone && raw.length >= 11) {
        delete this.formErrors.phone;
      }
    },

    validateForm() {
      const errors = {};
      if (!this.form.company_name || !this.form.company_name.trim()) {
        errors.company_name = 'Укажите название компании или ИП';
      }

      const binDigits = (this.form.bin || '').replace(/\D/g, '');
      if (binDigits.length !== 12) {
        errors.bin = 'БИН/ИИН должен содержать ровно 12 цифр';
      }

      if (!this.form.city) {
        errors.city = 'Выберите город поставки';
      }

      const phoneDigits = (this.form.phone || '').replace(/\D/g, '');
      if (phoneDigits.length < 11) {
        errors.phone = 'Укажите корректный номер телефона (+7 (7XX) XXX-XX-XX)';
      }

      this.formErrors = errors;
      return Object.keys(errors).length === 0;
    },

    async submitOrder() {
      if (this.cartItems.length === 0) {
        alert('Корзина пуста. Добавьте товары из каталога.');
        return;
      }

      if (!this.validateForm()) {
        this.haptic('error');
        return;
      }

      this.isSubmitting = true;

      const tg = window.Telegram?.WebApp;
      const tgUser = tg?.initDataUnsafe?.user || {};
      const tgChat = tg?.initDataUnsafe?.chat || {};
      const chatId = tgUser.id || tgChat.id || null;

      const orderData = {
        event: "web_app_order",
        company_name: this.form.company_name.trim(),
        bin: this.form.bin.trim(),
        city: this.form.city,
        client_name: (this.form.client_name || '').trim(),
        phone: this.form.phone.trim(),
        chat_id: chatId,
        tg_user_id: tgUser.id || null,
        tg_username: tgUser.username || null,
        items: this.cartItems.map(i => ({
          sku: i.sku,
          name: i.name,
          price: i.price,
          qty: i.qty,
          line_total: Math.round(i.price * i.qty),
          system_code: i.system_code
        })),
        total_amount: Math.round(this.cartTotalAmount)
      };

      console.log('Tork Mini App — Submitting order payload:', orderData);
      window.__lastTorkOrderData = orderData; // Useful for automated checks & debugging

      // 1. Direct HTTP webhook submission to n8n (works from inline button, menu button, direct link)
      try {
        const resp = await fetch('/webhook/web-app-order', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(orderData)
        });
        if (resp.ok) {
          console.log('Order submitted successfully via webhook');
        } else {
          console.warn('Webhook responded with status', resp.status);
        }
      } catch (err) {
        console.warn('Direct webhook fetch failed:', err);
      }

      // 2. Also call Telegram WebApp sendData if supported (e.g. keyboard button)
      if (tg && typeof tg.sendData === 'function') {
        try {
          tg.sendData(JSON.stringify(orderData));
        } catch (e) {
          console.warn('Telegram.WebApp.sendData not allowed or failed:', e);
        }
      }

      this.isSubmitting = false;
      this.haptic('success');
      this.submittedOrderData = orderData;
      this.orderSuccess = true;

      // If inside Telegram WebApp, automatically close after a brief delay so user returns to chat
      if (tg && typeof tg.close === 'function') {
        setTimeout(() => {
          try {
            tg.close();
          } catch (e) {
            console.warn('Could not close Telegram WebApp window:', e);
          }
        }, 1800);
      }
    },

    copyPayload() {
      if (!this.submittedOrderData) return;
      const text = JSON.stringify(this.submittedOrderData, null, 2);
      navigator.clipboard.writeText(text).then(() => {
        this.copiedPayload = true;
        setTimeout(() => { this.copiedPayload = false; }, 2000);
      });
    },

    handleImageError(event) {
      event.target.src = FALLBACK_IMAGE_SVG;
    },

    getColorBadge(color) {
      const c = (color || '').toLowerCase();
      if (c === 'white') {
        return { label: 'Белый', dotClass: 'bg-white border border-slate-300' };
      }
      if (c === 'black') {
        return { label: 'Черный', dotClass: 'bg-slate-900 border border-slate-700' };
      }
      if (c === 'stainless_steel' || c === 'steel' || c === 'metal') {
        return { label: 'Сталь', dotClass: 'bg-gradient-to-tr from-slate-400 to-slate-200 border border-slate-400' };
      }
      return null;
    },

    haptic(type) {
      if (window.Telegram?.WebApp?.HapticFeedback) {
        const hf = window.Telegram.WebApp.HapticFeedback;
        try {
          if (type === 'impact') hf.impactOccurred('light');
          else if (type === 'selection') hf.selectionChanged();
          else if (type === 'success') hf.notificationOccurred('success');
          else if (type === 'error') hf.notificationOccurred('error');
          else if (type === 'notification') hf.notificationOccurred('warning');
        } catch (e) {
          // Ignore
        }
      }
    }
  }
}).mount('#app');
