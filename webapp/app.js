const { createApp } = Vue;

const FALLBACK_IMAGE_SVG = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300" fill="none"><rect width="300" height="300" fill="%23F1F5F9"/><rect x="80" y="60" width="140" height="180" rx="16" fill="%23003865" fill-opacity="0.1" stroke="%23003865" stroke-width="3" stroke-dasharray="6 6"/><circle cx="150" cy="140" r="28" fill="%23009FDA" fill-opacity="0.2"/><path d="M140 140H160M150 130V150" stroke="%23009FDA" stroke-width="3" stroke-linecap="round"/><text x="150" y="210" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="bold" fill="%23003865">TORK</text></svg>`;

createApp({
  data() {
    return {
      products: [],
      loading: true,
      error: null,
      selectedZone: 'zone_wash',
      selectedCategory: 'dispenser', // 'dispenser' | 'all' | 'refill'
      searchQuery: '',
      preselectedSku: null,
      selectedProduct: null, // Modal preview
      selectedKit: {}, // Keyed by sku: { product: {...}, count: 1 }
      showKitDrawer: false,
      selectionSuccess: false,
      isSubmitting: false,
      submittedSelectionData: null,
      copiedPayload: false,
      activeTab: 'catalog', // 'catalog' | 'prices' | 'managers'
      adminManagers: [],
      newManagerId: '',
      newManagerName: '',
      newManagerRole: 'manager',
      isSavingPrice: false,
      editingPriceSku: null,
      editingPriceVal: null,
      adminToast: null,
      showKpModal: false,
      isGeneratingKp: false,
      kpGeneratedSuccess: false,
      generatedKpFilename: '',
      kpForm: {
        company_name: '',
        client_facility: 'Гостиничный комплекс, 5 этажей, 42 санузла',
        client_city: 'г. Астана, Казахстан',
        manager_name: '',
        manager_phone: '',
        manager_tg: ''
      },
      zones: [
        { id: 'zone_wash', label: 'Мытье рук', icon: '🧼' },
        { id: 'zone_toilet', label: 'Туалетная', icon: '🚽' },
        { id: 'zone_accessories', label: 'Корзины / Акс.', icon: '🗑️' },
        { id: 'zone_wiping', label: 'Протирка', icon: '🧻' }
      ]
    };
  },

  computed: {
    currentZoneProducts() {
      return (this.products || []).filter(p => p.zone === this.selectedZone);
    },

    zoneCounts() {
      const counts = { all: 0, dispenser: 0, refill: 0 };
      const current = (typeof this.currentZoneProducts === 'function' 
        ? this.currentZoneProducts() 
        : this.currentZoneProducts) || [];
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
          (p.sku && p.sku.toLowerCase().includes(q)) || 
          (p.name && p.name.toLowerCase().includes(q)) ||
          (p.system_code && p.system_code.toLowerCase().includes(q))
        );
      }

      const zoneProducts = (typeof this.currentZoneProducts === 'function' 
        ? this.currentZoneProducts() 
        : this.currentZoneProducts) || [];

      return zoneProducts.filter(p => {
        if (this.selectedCategory === 'all') return true;
        return p.category === this.selectedCategory;
      });
    },

    kitItemsList() {
      return Object.values(this.selectedKit).filter(item => item && item.count > 0);
    },

    totalKitCount() {
      return this.kitItemsList.reduce((sum, item) => sum + (item.count || 0), 0);
    },

    totalKitItemsCount() {
      return this.kitItemsList.length;
    },

    totalKitPrice() {
      return this.kitItemsList.reduce((sum, item) => sum + ((item.product?.price || 0) * (item.count || 1)), 0);
    }
  },

  mounted() {
    this.initTelegram();
    this.loadCatalog();
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('mode') === 'create_kp' || urlParams.get('action') === 'create_kp') {
      setTimeout(() => {
        this.openKpModal();
      }, 300);
    }
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
        let resp = await fetch('products.json');
        if (!resp.ok) {
          resp = await fetch('/app/products.json');
        }

        if (!resp.ok) {
          throw new Error(`Ошибка загрузки каталога (код: ${resp.status})`);
        }

        const data = await resp.json();
        this.products = data;
        this.loading = false;
        this.handlePreselectedSku();
      } catch (err) {
        console.error('Ошибка получения каталога products.json:', err);
        this.error = err.message || 'Не удалось загрузить каталог товаров';
        this.loading = false;
      }
    },

    handlePreselectedSku() {
      const urlParams = new URLSearchParams(window.location.search);
      const preselect = urlParams.get('preselect_sku') || urlParams.get('sku');
      if (preselect) {
        this.preselectedSku = String(preselect).trim();
        const item = this.products.find(p => p.sku === this.preselectedSku);
        if (item) {
          this.selectedZone = item.zone;
          this.selectedCategory = item.category || 'all';
          this.addItemToKit(item);
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

    openProductModal(product) {
      this.selectedProduct = product;
      this.selectionSuccess = false;
      this.haptic('impact');
    },

    closeProductModal() {
      this.selectedProduct = null;
      this.selectionSuccess = false;
    },

    getItemCount(sku) {
      return this.selectedKit[sku]?.count || 0;
    },

    addItemToKit(product) {
      if (!product || !product.sku) return;
      const sku = product.sku;
      if (!this.selectedKit[sku]) {
        this.selectedKit[sku] = {
          product: product,
          count: 1
        };
      } else {
        this.selectedKit[sku].count++;
      }
      this.haptic('impact');
    },

    removeItemFromKit(sku) {
      if (!this.selectedKit[sku]) return;
      if (this.selectedKit[sku].count > 1) {
        this.selectedKit[sku].count--;
      } else {
        delete this.selectedKit[sku];
      }
      this.haptic('selection');
    },

    deleteFromKit(sku) {
      if (this.selectedKit[sku]) {
        delete this.selectedKit[sku];
        this.haptic('impact');
      }
    },

    clearKit() {
      this.selectedKit = {};
      this.haptic('notification');
    },

    toggleKitDrawer() {
      this.showKitDrawer = !this.showKitDrawer;
      this.haptic('selection');
    },

    async submitKit() {
      if (this.kitItemsList.length === 0 || this.isSubmitting) return;

      this.isSubmitting = true;
      this.haptic('impact');

      const tg = window.Telegram?.WebApp;
      const tgUser = tg?.initDataUnsafe?.user || {};
      const tgChat = tg?.initDataUnsafe?.chat || {};
      const urlParams = new URLSearchParams(window.location.search);
      const urlUserId = urlParams.get('user_id') || urlParams.get('telegram_id') || urlParams.get('chat_id');
      const tgUserId = tgUser.id || (urlUserId ? parseInt(urlUserId) : null) || 5699064827;
      const chatId = tgChat.id || tgUserId;

      const itemsPayload = this.kitItemsList.map(item => ({
        sku: String(item.product.sku).trim(),
        name: item.product.name,
        category: item.product.category,
        product_type: item.product.product_type,
        system_code: item.product.system_code,
        color: item.product.color,
        price: item.product.price,
        image_url: item.product.image_url,
        count: item.count || 1,
        dimensions_cm: item.product.dimensions_cm || null
      }));

      const primaryItem = itemsPayload[0];

      const action = this.totalKitCount > 1 ? 'select_kit' : 'select_dispenser';

      const payload = {
        action: action,
        event: action,
        chat_id: chatId,
        tg_user_id: tgUserId,
        tg_username: tgUser.username || null,
        items: itemsPayload,
        // Compatibility fields for single-item nodes:
        sku: primaryItem.sku,
        name: primaryItem.name,
        category: primaryItem.category,
        product_type: primaryItem.product_type,
        system_code: primaryItem.system_code,
        color: primaryItem.color,
        price: primaryItem.price,
        image_url: primaryItem.image_url,
        timestamp: new Date().toISOString()
      };

      console.log('Tork Mini App — Kit selected payload:', payload);
      window.__lastTorkSelectionData = payload;

      // 1. Send to Backend API
      try {
        const resp = await fetch('/api/manager/select-kit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!resp.ok) {
          const errText = await resp.text();
          let errMsg = `Ошибка сервера (${resp.status})`;
          try {
            const errJson = JSON.parse(errText);
            errMsg = errJson.detail || errMsg;
          } catch (_) {}
          throw new Error(errMsg);
        }
      } catch (e) {
        console.error('API /api/manager/select-kit error:', e);
        this.isSubmitting = false;
        this.haptic('error');
        this.showAdminToast('Ошибка сохранения выбора: ' + e.message, 'error');
        return;
      }

      // 2. Telegram WebApp sendData fallback (if opened from reply keyboard)
      if (tg && typeof tg.sendData === 'function') {
        try {
          tg.sendData(JSON.stringify(payload));
        } catch (e) {
          console.warn('Telegram.WebApp.sendData error:', e);
        }
      }

      this.isSubmitting = false;
      this.haptic('success');
      this.submittedSelectionData = payload;
      this.selectionSuccess = true;
      this.showKitDrawer = false;

      // Close Mini App after brief delay to return manager to Telegram chat
      if (tg && typeof tg.close === 'function') {
        setTimeout(() => {
          try {
            tg.close();
          } catch (e) {
            console.warn('Telegram close failed:', e);
          }
        }, 1200);
      }
    },

    confirmDispenserSelection(product) {
      if (!product) return;
      this.addItemToKit(product);
      this.submitKit();
    },

    quickSelect(product) {
      this.confirmDispenserSelection(product);
    },

    copyPayload() {
      if (!this.submittedSelectionData) return;
      const text = JSON.stringify(this.submittedSelectionData, null, 2);
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
    },

    switchTab(tab) {
      this.activeTab = tab;
      this.haptic('selection');
      if (tab === 'managers') {
        this.loadAdminManagers();
      }
    },

    async loadAdminManagers() {
      try {
        const resp = await fetch('/api/admin-tg/managers');
        if (resp.ok) {
          this.adminManagers = await resp.json();
        }
      } catch (e) {
        console.error('Failed to load managers:', e);
      }
    },

    async addManager() {
      if (!this.newManagerId || !this.newManagerName) {
        this.showAdminToast('Укажите Telegram ID и ФИО', 'error');
        return;
      }
      try {
        const resp = await fetch('/api/admin-tg/managers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            telegram_id: parseInt(this.newManagerId),
            full_name: this.newManagerName.trim(),
            role: this.newManagerRole
          })
        });
        if (resp.ok) {
          this.showAdminToast('✅ Менеджер успешно добавлен!');
          this.newManagerId = '';
          this.newManagerName = '';
          this.loadAdminManagers();
        } else {
          this.showAdminToast('Ошибка добавления менеджера', 'error');
        }
      } catch (e) {
        this.showAdminToast('Сетевая ошибка: ' + e.message, 'error');
      }
    },

    async toggleManager(tgId, currentStatus) {
      try {
        const resp = await fetch(`/api/admin-tg/managers/${tgId}/toggle`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_active: !currentStatus })
        });
        if (resp.ok) {
          this.showAdminToast(currentStatus ? 'Доступ приостановлен' : 'Доступ активирован');
          this.loadAdminManagers();
        }
      } catch (e) {
        this.showAdminToast('Ошибка смены статуса', 'error');
      }
    },

    startEditPrice(sku, currentPrice) {
      this.editingPriceSku = sku;
      this.editingPriceVal = Math.round(currentPrice || 0);
    },

    cancelEditPrice() {
      this.editingPriceSku = null;
      this.editingPriceVal = null;
    },

    async saveProductPrice(sku) {
      if (this.editingPriceVal === null || isNaN(this.editingPriceVal)) return;
      this.isSavingPrice = true;
      try {
        const resp = await fetch(`/api/admin-tg/prices/${sku}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ price_kzt: parseFloat(this.editingPriceVal) })
        });
        if (resp.ok) {
          const res = await resp.json();
          const prod = this.products.find(p => p.sku === sku);
          if (prod) {
            prod.price = res.product.price_kzt;
          }
          this.showAdminToast(`✅ Цена SKU ${sku} обновлена!`);
          this.editingPriceSku = null;
          this.editingPriceVal = null;
        } else {
          this.showAdminToast('Ошибка сохранения цены', 'error');
        }
      } catch (e) {
        this.showAdminToast('Ошибка: ' + e.message, 'error');
      } finally {
        this.isSavingPrice = false;
      }
    },

    downloadExcelPricelist() {
      window.open('/api/admin-tg/prices/export-excel', '_blank');
    },

    showAdminToast(msg, type = 'success') {
      this.adminToast = { msg, type };
      this.haptic(type === 'error' ? 'error' : 'success');
      setTimeout(() => { this.adminToast = null; }, 3000);
    },

    async openKpModal() {
      this.showKpModal = true;
      this.kpGeneratedSuccess = false;
      this.haptic('selection');

      const tg = window.Telegram?.WebApp;
      const tgUser = tg?.initDataUnsafe?.user || {};
      const urlParams = new URLSearchParams(window.location.search);
      const urlUserId = urlParams.get('user_id') || urlParams.get('telegram_id') || urlParams.get('chat_id');
      const tgId = tgUser.id || (urlUserId ? parseInt(urlUserId) : null) || 5699064827;

      try {
        const resp = await fetch(`/api/manager/form-defaults?telegram_id=${tgId}`);
        if (resp.ok) {
          const data = await resp.json();
          if (data.ok && data.defaults) {
            const d = data.defaults;
            if (!this.kpForm.manager_name) this.kpForm.manager_name = d.manager_name || 'Ерлан Кубесов';
            if (!this.kpForm.manager_phone) this.kpForm.manager_phone = d.manager_phone || '+7 (777) 777-77-77';
            if (!this.kpForm.manager_tg) this.kpForm.manager_tg = d.manager_tg || '@erlan_tork_kz';
            if (!this.kpForm.client_city) this.kpForm.client_city = d.client_city || 'г. Астана, Казахстан';
            if (!this.kpForm.company_name && d.company_name) this.kpForm.company_name = d.company_name;
            if (!this.kpForm.client_facility && d.client_facility) this.kpForm.client_facility = d.client_facility;

            // If manager opened KP form directly, restore chosen kit from session so nothing is unlinked
            if (this.kitItemsList.length === 0 && Array.isArray(d.selected_bundle) && d.selected_bundle.length > 0) {
              for (const it of d.selected_bundle) {
                if (it && it.sku) {
                  const prod = this.products.find(p => p.sku === it.sku) || it;
                  this.selectedKit[it.sku] = {
                    product: prod,
                    count: it.count || 1
                  };
                }
              }
            }
          }
        }
      } catch (e) {
        console.warn('Could not fetch form defaults:', e);
        if (!this.kpForm.manager_name) this.kpForm.manager_name = 'Ерлан Кубесов';
        if (!this.kpForm.manager_phone) this.kpForm.manager_phone = '+7 (777) 777-77-77';
        if (!this.kpForm.manager_tg) this.kpForm.manager_tg = '@erlan_tork_kz';
      }
    },

    closeKpModal() {
      this.showKpModal = false;
      this.kpGeneratedSuccess = false;
    },

    async submitGenerateKp() {
      if (!this.kpForm.company_name || !this.kpForm.company_name.trim()) {
        this.showAdminToast('Укажите наименование компании клиента (например: ТОО «РУБИЛЬНИК»)', 'error');
        return;
      }
      if (!this.kpForm.client_facility || !this.kpForm.client_facility.trim()) {
        this.showAdminToast('Укажите тип объекта и масштаб (например: Гостиничный комплекс, 5 этажей, 42 санузла)', 'error');
        return;
      }

      this.isGeneratingKp = true;
      this.haptic('impact');

      const tg = window.Telegram?.WebApp;
      const tgUser = tg?.initDataUnsafe?.user || {};
      const tgChat = tg?.initDataUnsafe?.chat || {};
      const urlParams = new URLSearchParams(window.location.search);
      const urlUserId = urlParams.get('user_id') || urlParams.get('telegram_id') || urlParams.get('chat_id');
      const tgId = tgUser.id || (urlUserId ? parseInt(urlUserId) : null) || 5699064827;
      const chatId = tgChat.id || tgId;

      const items = this.kitItemsList.length > 0 ? this.kitItemsList.map(item => ({
        sku: String(item.product.sku).trim(),
        name: item.product.name,
        system_code: item.product.system_code,
        color: item.product.color,
        price: item.product.price,
        count: item.count || 1
      })) : null;

      const payload = {
        telegram_id: tgId,
        chat_id: chatId,
        company_name: this.kpForm.company_name.trim(),
        client_facility: this.kpForm.client_facility.trim(),
        client_city: this.kpForm.client_city.trim() || 'г. Астана, Казахстан',
        manager_name: this.kpForm.manager_name.trim() || undefined,
        manager_phone: this.kpForm.manager_phone.trim() || undefined,
        manager_tg: this.kpForm.manager_tg.trim() || undefined,
        items: items,
        send_to_telegram: true
      };

      try {
        const resp = await fetch('/api/manager/generate-kp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (resp.ok) {
          const res = await resp.json();
          this.isGeneratingKp = false;
          this.kpGeneratedSuccess = true;
          this.generatedKpFilename = res.filename || 'КП_Tork.pdf';
          this.haptic('success');
          this.showAdminToast('✅ КП успешно сформировано и отправлено в чат!');

          if (tg && typeof tg.close === 'function') {
            setTimeout(() => {
              try {
                tg.close();
              } catch (e) {}
            }, 1800);
          }
        } else {
          const errText = await resp.text();
          let errMsg = 'Ошибка генерации КП';
          try {
            const errJson = JSON.parse(errText);
            errMsg = errJson.detail || errMsg;
          } catch (_) {
            errMsg = `Ошибка сервера (${resp.status}): ${errText.slice(0, 100)}`;
          }
          throw new Error(errMsg);
        }
      } catch (err) {
        this.isGeneratingKp = false;
        this.haptic('error');
        this.showAdminToast('Ошибка: ' + err.message, 'error');
      }
    }
  }
}).mount('#app');
