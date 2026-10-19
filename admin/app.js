// Tork B2B Dashboard Vue 3 Application
const { createApp } = Vue;

createApp({
  data() {
    return {
      currentView: 'login', // 'login' | 'dashboard'
      activeTab: 'orders', // 'orders' | 'analytics' | 'catalog'
      token: localStorage.getItem('tork_admin_token') || '',
      currentUser: null,

      // Login form state
      loginEmail: '',
      loginPassword: '',
      showPassword: false,
      isLoggingIn: false,
      loginError: '',

      // Orders state
      orders: [],
      totalOrdersCount: 0,
      totalPages: 1,
      currentPage: 1,
      limit: 20,
      isLoadingOrders: false,

      // Orders Filters
      selectedStatus: '',
      selectedDistributorId: '',
      searchQuery: '',
      searchDebounceTimer: null,

      // Status counters for KPI blocks
      statusCounts: {
        NEW: 0,
        IN_PROGRESS: 0,
        INVOICE_SENT: 0,
        TEST_DRIVE: 0,
        COMPLETED: 0,
        CANCELLED: 0
      },

      // Modal / Drawer state
      selectedOrder: null,
      modalStatus: 'NEW',
      modalNotes: '',
      modalItems: [],
      isSavingModal: false,

      // PDF download tracking
      downloadingPdfId: null,

      // -------------------------------------------------------------
      // Sprint 3: Analytics state
      // -------------------------------------------------------------
      analyticsSummary: {
        total_revenue_kzt: 0,
        total_orders_count: 0,
        average_check_kzt: 0,
        by_region: [],
        by_channel: {
          direct_catalog_count: 0,
          ai_fitting_count: 0
        }
      },
      topProducts: [],
      slaAnalytics: {
        average_response_time_minutes: 0,
        average_response_time_formatted: '0 мин',
        processed_orders_count: 0,
        breached_leads_count: 0,
        breached_leads: []
      },
      isLoadingAnalytics: false,

      // -------------------------------------------------------------
      // Sprint 3: Catalog Matrix state
      // -------------------------------------------------------------
      catalogProducts: [],
      isLoadingCatalog: false,
      catalogSearch: '',
      selectedCatalogCategory: '',
      selectedCatalogSystem: '',
      selectedCatalogStatus: '', // '' | 'active' | 'inactive'
      togglingSku: null,

      // Toast notifications
      toasts: [],
      toastIdCounter: 0
    };
  },

  computed: {
    currentUserBranchLabel() {
      if (!this.currentUser) return '';
      if (this.currentUser.role === 'vendor_admin') return 'Вендор Tork';
      const id = this.currentUser.distributor_id;
      if (id === 1) return 'Астана';
      if (id === 2) return 'Алматы';
      if (id === 3) return 'Шымкент';
      return this.currentUser.organization || 'Филиал';
    },

    visiblePages() {
      const pages = [];
      const total = this.totalPages;
      const cur = this.currentPage;
      const start = Math.max(1, cur - 2);
      const end = Math.min(total, cur + 2);
      for (let i = start; i <= end; i++) {
        pages.push(i);
      }
      return pages;
    },

    // Catalog computed helpers
    catalogSystems() {
      const set = new Set();
      this.catalogProducts.forEach(p => {
        if (p.system_code && p.system_code !== '—') {
          set.add(p.system_code.trim());
        }
      });
      return Array.from(set).sort();
    },

    filteredCatalogProducts() {
      let list = this.catalogProducts;
      const q = (this.catalogSearch || '').toLowerCase().trim();

      if (q) {
        list = list.filter(p => 
          (p.sku && p.sku.toLowerCase().includes(q)) ||
          (p.name && p.name.toLowerCase().includes(q)) ||
          (p.system_code && p.system_code.toLowerCase().includes(q))
        );
      }

      if (this.selectedCatalogCategory) {
        list = list.filter(p => p.category === this.selectedCatalogCategory);
      }

      if (this.selectedCatalogSystem) {
        list = list.filter(p => p.system_code === this.selectedCatalogSystem);
      }

      if (this.selectedCatalogStatus === 'active') {
        list = list.filter(p => p.is_active_in_catalog);
      } else if (this.selectedCatalogStatus === 'inactive') {
        list = list.filter(p => !p.is_active_in_catalog);
      }

      return list;
    },

    catalogStats() {
      const total = this.catalogProducts.length;
      let active = 0;
      let inactive = 0;
      this.catalogProducts.forEach(p => {
        if (p.is_active_in_catalog) active++;
        else inactive++;
      });
      return { total, active, inactive };
    },

    channelStats() {
      const direct = this.analyticsSummary?.by_channel?.direct_catalog_count || 0;
      const ai = this.analyticsSummary?.by_channel?.ai_fitting_count || 0;
      const sum = direct + ai;
      const directPercent = sum > 0 ? Math.round((direct / sum) * 100) : 0;
      const aiPercent = sum > 0 ? (100 - directPercent) : 0;
      return { direct, ai, sum, directPercent, aiPercent };
    }
  },

  mounted() {
    // Check saved token and user
    const savedUser = localStorage.getItem('tork_admin_user');
    if (this.token && savedUser) {
      try {
        this.currentUser = JSON.parse(savedUser);
        this.currentView = 'dashboard';
        this.fetchOrders(1);
        this.fetchStatusStats();
      } catch (e) {
        this.logout();
      }
    } else {
      this.currentView = 'login';
    }
  },

  methods: {
    // =========================================================================
    // API Helper with Automatic Bearer Header & 401 Interception
    // =========================================================================
    async apiFetch(endpoint, options = {}) {
      const headers = options.headers ? { ...options.headers } : {};
      if (this.token) {
        headers['Authorization'] = `Bearer ${this.token}`;
      }
      const config = { ...options, headers };

      try {
        const res = await fetch(endpoint, config);
        if (res.status === 401) {
          this.logout();
          this.showToast('Сессия истекла. Пожалуйста, выполните вход повторно.', 'error');
          throw new Error('Unauthorized');
        }
        return res;
      } catch (err) {
        if (err.message !== 'Unauthorized') {
          console.error('API Fetch Error:', err);
        }
        throw err;
      }
    },

    // =========================================================================
    // Auth & Navigation
    // =========================================================================
    fillQuickLogin(email) {
      this.loginEmail = email;
      this.loginPassword = 'TorkKZ2026!';
      this.handleLogin();
    },

    async handleLogin() {
      if (!this.loginEmail || !this.loginPassword) {
        this.loginError = 'Укажите корпоративный email и пароль';
        return;
      }

      this.isLoggingIn = true;
      this.loginError = '';

      try {
        const res = await fetch('/api/admin/auth/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            email: this.loginEmail,
            password: this.loginPassword
          })
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || 'Неверный email или пароль');
        }

        this.token = data.access_token;
        this.currentUser = data.user;
        localStorage.setItem('tork_admin_token', this.token);
        localStorage.setItem('tork_admin_user', JSON.stringify(this.currentUser));

        this.currentView = 'dashboard';
        this.activeTab = 'orders';
        this.showToast(`Добро пожаловать, ${this.currentUser.full_name}!`, 'success');
        this.fetchOrders(1);
        this.fetchStatusStats();
      } catch (err) {
        this.loginError = err.message || 'Ошибка подключения к серверу';
      } finally {
        this.isLoggingIn = false;
      }
    },

    logout() {
      this.token = '';
      this.currentUser = null;
      localStorage.removeItem('tork_admin_token');
      localStorage.removeItem('tork_admin_user');
      this.currentView = 'login';
      this.activeTab = 'orders';
      this.orders = [];
    },

    switchTab(tab) {
      // Distributor manager is locked to 'orders'
      if (this.currentUser?.role !== 'vendor_admin' && tab !== 'orders') {
        return;
      }
      this.activeTab = tab;
      if (tab === 'analytics') {
        this.fetchAnalytics();
      } else if (tab === 'catalog') {
        this.fetchCatalogProducts();
      } else if (tab === 'orders') {
        this.fetchOrders(this.currentPage);
        this.fetchStatusStats();
      }
    },

    // =========================================================================
    // Sprint 3: Analytics Module
    // =========================================================================
    async fetchAnalytics() {
      this.isLoadingAnalytics = true;
      try {
        const [summaryRes, topRes, slaRes] = await Promise.all([
          this.apiFetch('/api/admin/analytics/summary'),
          this.apiFetch('/api/admin/analytics/top-products'),
          this.apiFetch('/api/admin/analytics/sla')
        ]);

        if (summaryRes.ok) {
          this.analyticsSummary = await summaryRes.json();
        }
        if (topRes.ok) {
          this.topProducts = await topRes.json();
        }
        if (slaRes.ok) {
          this.slaAnalytics = await slaRes.json();
        }
      } catch (err) {
        if (err.message !== 'Unauthorized') {
          this.showToast(err.message || 'Ошибка загрузки аналитики', 'error');
        }
      } finally {
        this.isLoadingAnalytics = false;
      }
    },

    jumpToOrderFromSla(orderId) {
      this.activeTab = 'orders';
      this.openOrderDetail(orderId);
    },

    // =========================================================================
    // Sprint 3: Catalog Matrix Management
    // =========================================================================
    async fetchCatalogProducts() {
      this.isLoadingCatalog = true;
      try {
        const res = await this.apiFetch('/api/admin/products');
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Ошибка загрузки товаров каталога');
        }
        this.catalogProducts = await res.json();
      } catch (err) {
        if (err.message !== 'Unauthorized') {
          this.showToast(err.message || 'Ошибка загрузки каталога', 'error');
        }
      } finally {
        this.isLoadingCatalog = false;
      }
    },

    async toggleProductStatus(product) {
      if (this.togglingSku === product.sku) return;
      this.togglingSku = product.sku;

      const previousStatus = product.is_active_in_catalog;
      // Optimistic update
      product.is_active_in_catalog = !previousStatus;

      try {
        const res = await this.apiFetch(`/api/admin/products/${product.sku}/toggle`, {
          method: 'PATCH'
        });

        if (!res.ok) {
          // Revert optimistic update
          product.is_active_in_catalog = previousStatus;
          const err = await res.json();
          throw new Error(err.detail || 'Не удалось обновить статус товара');
        }

        const data = await res.json();
        product.is_active_in_catalog = data.is_active_in_catalog;
        this.showToast(data.message, data.is_active_in_catalog ? 'success' : 'info');
      } catch (err) {
        product.is_active_in_catalog = previousStatus;
        this.showToast(err.message || 'Ошибка обновления статуса товара', 'error');
      } finally {
        this.togglingSku = null;
      }
    },

    // =========================================================================
    // Orders Registry & Filters
    // =========================================================================
    async fetchOrders(page = 1) {
      this.isLoadingOrders = true;
      this.currentPage = page;

      try {
        const params = new URLSearchParams();
        params.append('page', String(page));
        params.append('limit', String(this.limit));

        if (this.selectedStatus) {
          params.append('status', this.selectedStatus);
        }

        if (this.currentUser?.role === 'vendor_admin' && this.selectedDistributorId) {
          params.append('distributor_id', String(this.selectedDistributorId));
        }

        if (this.searchQuery.trim()) {
          params.append('search', this.searchQuery.trim());
        }

        const res = await this.apiFetch(`/api/admin/orders?${params.toString()}`);
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Ошибка получения списка заказов');
        }

        const data = await res.json();
        this.orders = data.items || [];
        this.totalOrdersCount = data.total || 0;
        this.totalPages = Math.max(1, data.pages || 1);
      } catch (err) {
        if (err.message !== 'Unauthorized') {
          this.showToast(err.message || 'Ошибка загрузки заказов', 'error');
        }
      } finally {
        this.isLoadingOrders = false;
      }
    },

    async fetchStatusStats() {
      try {
        const counts = { NEW: 0, IN_PROGRESS: 0, INVOICE_SENT: 0, TEST_DRIVE: 0, COMPLETED: 0, CANCELLED: 0 };
        const params = new URLSearchParams();
        params.append('limit', '100');
        if (this.currentUser?.role === 'vendor_admin' && this.selectedDistributorId) {
          params.append('distributor_id', String(this.selectedDistributorId));
        }
        const res = await this.apiFetch(`/api/admin/orders?${params.toString()}`);
        if (res.ok) {
          const data = await res.json();
          (data.items || []).forEach(o => {
            if (counts[o.order_status] !== undefined) {
              counts[o.order_status]++;
            }
          });
          this.statusCounts = counts;
        }
      } catch (e) {
        console.warn('Could not fetch status stats:', e);
      }
    },

    setStatusFilter(st) {
      this.selectedStatus = st;
      this.fetchOrders(1);
    },

    handleSearchDebounce() {
      clearTimeout(this.searchDebounceTimer);
      this.searchDebounceTimer = setTimeout(() => {
        this.fetchOrders(1);
      }, 350);
    },

    clearSearch() {
      this.searchQuery = '';
      this.fetchOrders(1);
    },

    goToPage(p) {
      if (p >= 1 && p <= this.totalPages) {
        this.fetchOrders(p);
      }
    },

    isOrderSlaBreached(order) {
      if (order.sla_breached) return true;
      if (order.order_status === 'NEW' && order.created_at) {
        const created = new Date(order.created_at).getTime();
        const now = Date.now();
        const diffHours = (now - created) / (1000 * 60 * 60);
        return diffHours > 2.0;
      }
      return false;
    },

    // =========================================================================
    // Order Detail & Modal Management
    // =========================================================================
    async openOrderDetail(orderId) {
      try {
        const res = await this.apiFetch(`/api/admin/orders/${orderId}`);
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Не удалось открыть детали заказа');
        }

        const data = await res.json();
        this.selectedOrder = data;
        this.modalStatus = data.order_status;
        this.modalNotes = data.manager_notes || '';

        // Extract items from bundle
        const bundle = data.selected_bundle;
        if (Array.isArray(bundle)) {
          this.modalItems = bundle;
        } else if (bundle && typeof bundle === 'object' && Array.isArray(bundle.items)) {
          this.modalItems = bundle.items;
        } else {
          this.modalItems = [];
        }
      } catch (err) {
        this.showToast(err.message || 'Ошибка загрузки карточки заказа', 'error');
      }
    },

    closeOrderDetail() {
      this.selectedOrder = null;
      this.modalItems = [];
    },

    async updateOrderStatus(order) {
      try {
        const res = await this.apiFetch(`/api/admin/orders/${order.id}/status`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            order_status: order.order_status
          })
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Не удалось обновить статус');
        }

        this.showToast(`Статус заказа #${order.kp_number || order.id} изменен на "${this.getStatusLabel(order.order_status)}"`, 'success');
        this.fetchStatusStats();
      } catch (err) {
        this.showToast(err.message || 'Ошибка обновления статуса', 'error');
        this.fetchOrders(this.currentPage);
      }
    },

    async saveOrderModal() {
      if (!this.selectedOrder) return;
      this.isSavingModal = true;

      try {
        const res = await this.apiFetch(`/api/admin/orders/${this.selectedOrder.id}/status`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            order_status: this.modalStatus,
            manager_notes: this.modalNotes
          })
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Не удалось сохранить изменения');
        }

        const updated = await res.json();
        this.selectedOrder.order_status = updated.order_status;
        this.selectedOrder.manager_notes = updated.manager_notes;

        // Also update in table list if present
        const tableItem = this.orders.find(o => o.id === this.selectedOrder.id);
        if (tableItem) {
          tableItem.order_status = updated.order_status;
        }

        this.showToast('Изменения и заметки успешно сохранены', 'success');
        this.fetchStatusStats();
      } catch (err) {
        this.showToast(err.message || 'Ошибка сохранения', 'error');
      } finally {
        this.isSavingModal = false;
      }
    },

    // =========================================================================
    // Gotenberg PDF Download
    // =========================================================================
    async downloadOrderPdf(order) {
      if (this.downloadingPdfId === order.id) return;
      this.downloadingPdfId = order.id;

      try {
        this.showToast(`Генерация PDF для КП #${order.kp_number || order.id}...`, 'info');

        const res = await this.apiFetch(`/api/admin/orders/${order.id}/pdf`);
        if (!res.ok) {
          let errDetail = 'Ошибка формирования коммерческого предложения';
          try {
            const err = await res.json();
            errDetail = err.detail || errDetail;
          } catch (_) {}
          throw new Error(errDetail);
        }

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        let filename = `KP_Tork_${order.kp_number || ('TKZ-' + String(order.id).padStart(6, '0'))}.pdf`;
        const disposition = res.headers.get('content-disposition');
        if (disposition && disposition.indexOf('filename=') !== -1) {
          const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
          if (matches != null && matches[1]) {
            filename = matches[1].replace(/['"]/g, '');
          }
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        this.showToast(`КП #${order.kp_number || order.id} успешно скачано`, 'success');
      } catch (err) {
        this.showToast(err.message || 'Ошибка генерации PDF', 'error');
      } finally {
        this.downloadingPdfId = null;
      }
    },

    // =========================================================================
    // UI Helpers & Formatters
    // =========================================================================
    formatCurrency(val) {
      if (val === null || val === undefined || isNaN(val)) return '0';
      return Math.round(Number(val)).toLocaleString('ru-RU');
    },

    formatDate(dateStr) {
      if (!dateStr) return '—';
      try {
        const d = new Date(dateStr);
        return d.toLocaleDateString('ru-RU', {
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        });
      } catch (e) {
        return dateStr;
      }
    },

    getStatusLabel(st) {
      const map = {
        NEW: 'Новый',
        IN_PROGRESS: 'В работе',
        INVOICE_SENT: 'Счет выставлен',
        TEST_DRIVE: 'Тест-драйв',
        COMPLETED: 'Завершен',
        CANCELLED: 'Отказ'
      };
      return map[st] || st;
    },

    getStatusBadgeClasses(st) {
      switch (st) {
        case 'NEW':
          return 'bg-blue-50 text-blue-700 border-blue-200';
        case 'IN_PROGRESS':
          return 'bg-amber-50 text-amber-700 border-amber-200';
        case 'INVOICE_SENT':
          return 'bg-purple-50 text-purple-700 border-purple-200';
        case 'TEST_DRIVE':
          return 'bg-emerald-50 text-emerald-700 border-emerald-200';
        case 'COMPLETED':
          return 'bg-teal-50 text-teal-700 border-teal-200';
        case 'CANCELLED':
          return 'bg-rose-50 text-rose-700 border-rose-200';
        default:
          return 'bg-slate-50 text-slate-700 border-slate-200';
      }
    },

    copyToClipboard(text, message = 'Скопировано!') {
      if (!text) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(String(text));
        this.showToast(message, 'info');
      } else {
        const el = document.createElement('textarea');
        el.value = String(text);
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        this.showToast(message, 'info');
      }
    },

    // =========================================================================
    // Toast Notification System
    // =========================================================================
    showToast(message, type = 'info') {
      const id = ++this.toastIdCounter;
      this.toasts.push({ id, message, type });
      setTimeout(() => {
        this.toasts = this.toasts.filter(t => t.id !== id);
      }, 4000);
    },

    getToastClasses(type) {
      switch (type) {
        case 'success':
          return 'bg-emerald-900/90 text-white border-emerald-700';
        case 'error':
          return 'bg-rose-900/90 text-white border-rose-700';
        case 'info':
        default:
          return 'bg-[#003865]/95 text-white border-blue-500';
      }
    },

    getToastIcon(type) {
      switch (type) {
        case 'success': return '✅';
        case 'error': return '⚠️';
        default: return 'ℹ️';
      }
    }
  }
}).mount('#app');
