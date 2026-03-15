/**
 * User & Organization Management Controller
 * Provides a richer admin experience with filtering, sorting, and robust API handling.
 */

function userManagementPage(config = {}) {
    const settings = {
        currentUserRole: config.currentUserRole || "user",
        currentUserId: config.currentUserId ?? null,
        canManageUsers: config.canManageUsers !== false,
        isSuperAdmin: !!config.isSuperAdmin,
        isOrgAdmin: !!config.isOrgAdmin,
        currentUserOrgId: config.currentUserOrgId ?? null,
        currentUserOrgName: config.currentUserOrgName || "",
    };

    const roleDefinitions = [
        { value: "super_admin", label: "Super Admin", restricted: true },
        { value: "admin", label: "Administrator" },
        { value: "doctor", label: "Doctor" },
        { value: "nurse", label: "Nurse" },
        { value: "user", label: "Standard User" },
    ];

    const organizationTypes = [
        { value: "hospital", label: "Hospital" },
        { value: "clinic", label: "Clinic" },
        { value: "ngo", label: "NGO / Non-profit" },
        { value: "platform", label: "Platform" },
    ];

    const sortOptions = [
        { value: "recent", label: "Latest activity" },
        { value: "name_asc", label: "Name A → Z" },
        { value: "name_desc", label: "Name Z → A" },
        { value: "role", label: "Role" },
    ];

    return {
        // Config
        settings,
        roleDefinitions,
        organizationTypes,
        sortOptions,
        
        // Expose settings for template access
        isSuperAdmin: settings.isSuperAdmin,
        isOrgAdmin: settings.isOrgAdmin,
        currentUserOrgId: settings.currentUserOrgId,
        currentUserOrgName: settings.currentUserOrgName,

        // State
        activeTab: "users",
        loadingStats: false,
        loadingUsers: false,
        loadingOrganizations: false,

        search: "",
        orgSearch: "",
        roleFilter: "",
        statusFilter: "",
        organizationFilter: "",
        sortBy: sortOptions[0].value,

        stats: {
            totalUsers: 0,
            adminUsers: 0,
            activeUsers: 0,
            organizations: 0,
        },

        users: [],
        organizations: [],
        filteredUsers: [],
        filteredOrganizations: [],

        pagination: {
            page: 1,
            limit: 50,
            total: 0,
            pages: 1,
        },

        selectedUsers: [],
        error: null,
        lastSyncedAt: null,
        metricsListener: null,

        // Modal state
        showAddUserModal: false,
        showEditUserModal: false,
        showViewUserModal: false,
        showAddOrgModal: false,
        showEditOrgModal: false,
        showAssignModal: false,

        // Forms
        newUser: {
            username: "",
            email: "",
            password: "",
            full_name: "",
            role: settings.isSuperAdmin ? "admin" : "user",
            organization_id: "",
            is_active: true,
        },
        editUserForm: {
            id: null,
            username: "",
            email: "",
            full_name: "",
            role: "user",
            organization_id: "",
            is_active: true,
            password: "",
        },
        newOrg: {
            name: "",
            type: "hospital",
            email: "",
            contact: "",
            is_active: true,
        },
        editOrgForm: {
            id: null,
            name: "",
            type: "hospital",
            email: "",
            contact: "",
            is_active: true,
        },

        selectedUser: null,
        selectedOrg: null,
        selectedUserForAssignment: null,
        assignForm: {
            user_id: null,
            assigned_to_id: ""
        },

        async init() {
            this.metricsListener = (event) => {
                if (event?.detail) {
                    this.updateStats(event.detail);
                }
            };
            window.addEventListener("admin:metrics-updated", this.metricsListener);

            await this.loadStats();
            await Promise.all([this.loadOrganizations(), this.loadUsers()]);
        },

        destroy() {
            if (this.metricsListener) {
                window.removeEventListener("admin:metrics-updated", this.metricsListener);
                this.metricsListener = null;
            }
        },

        notify(title, message, type = "info") {
            try {
                const store = Alpine.store("admin");
                if (store?.showNotification) {
                    store.showNotification(title, message, type);
                    return;
                }
            } catch (error) {
                console.warn("Notification store not available:", error);
            }
            console.log(`[${type}] ${title}: ${message}`);
        },

        setError(title, message, scope = "users") {
            const next = { title, message, scope };
            if (!this.error || this.error.title !== title || this.error.message !== message) {
                this.notify(title, message, "warning");
            }
            this.error = next;
        },

        clearError(scope = null) {
            if (!this.error) return;
            if (!scope || this.error.scope === scope) {
                this.error = null;
            }
        },

        async retry(scope = null) {
            switch (scope) {
                case "stats":
                    await this.loadStats();
                    break;
                case "organizations":
                    await this.loadOrganizations();
                    break;
                case "users":
                    await this.loadUsers();
                    break;
                default:
                    await Promise.all([this.loadStats(), this.loadOrganizations(), this.loadUsers()]);
            }
        },

        hasToken() {
            const token = localStorage.getItem("access_token");
            return Boolean(token);
        },

        authHeaders(extra = {}) {
            const token = localStorage.getItem("access_token");
            return token
                ? { Authorization: `Bearer ${token}`, ...extra }
                : extra;
        },

        async safeParse(response) {
            try {
                if (response.status === 204) return null;
                return await response.json();
            } catch (error) {
                return {};
            }
        },

        async loadStats() {
            this.loadingStats = true;
            this.clearError("stats");

            try {
                const response = await fetch("/api/v1/admin/stats", {
                    credentials: 'include',  // Include cookies for session auth
                    headers: this.authHeaders(),
                });

                console.log('Stats response status:', response.status);

                if (response.ok) {
                    const data = await this.safeParse(response);
                    console.log('Stats data received:', data);
                    
                    // Handle both formats: flat (totalUsers) and nested (users.total)
                    this.stats.totalUsers = data.totalUsers || data.total_users || data.users?.total || 0;
                    this.stats.adminUsers = data.adminUsers || data.admin_users || data.users?.admin || 0;
                    this.stats.activeUsers = data.activeUsers || data.active_users || data.users?.active || 0;
                    this.stats.organizations = data.organizations || data.total_organizations || data.organizations?.total || 0;
                    
                    console.log('Stats parsed:', this.stats);
                    this.clearError("stats");
                } else if (response.status === 401 || response.status === 403) {
                    // Not authenticated or no permission - use mock data
                    console.log('Not authenticated, using mock stats');
                    this.loadMockStats();
                } else {
                    throw new Error("API responded with an error.");
                }
            } catch (error) {
                console.error("Error loading stats:", error);
                this.setError("Stats unavailable", "Working with sample metrics right now.", "stats");
                this.loadMockStats();
            } finally {
                this.loadingStats = false;
            }
        },

        async loadUsers() {
            this.loadingUsers = true;
            this.clearError("users");

            try {
                const params = new URLSearchParams({
                    page: this.pagination.page,
                    limit: this.pagination.limit,
                    search: this.search || "",
                    role: this.roleFilter || "",
                    status: this.statusFilter || "",
                    sort_by: this.sortBy,
                });

                const response = await fetch(`/api/v1/admin/users?${params.toString()}`, {
                    credentials: 'include',  // Include cookies for session auth
                    headers: this.authHeaders(),
                });

                if (!response.ok) {
                    if (response.status === 401 || response.status === 403) {
                        // Not authenticated - use mock data
                        this.loadMockUsers();
                        return;
                    }
                    const errorBody = await this.safeParse(response);
                    throw new Error(errorBody?.detail || "Failed to load users.");
                }

                const data = await this.safeParse(response);
                const list = Array.isArray(data?.users)
                    ? data.users
                    : Array.isArray(data)
                        ? data
                        : Array.isArray(data?.items)
                            ? data.items
                            : [];

                this.users = list;
                if (data?.pagination) {
                    this.pagination = {
                        page: data.pagination.page || 1,
                        limit: data.pagination.limit || this.pagination.limit,
                        total: data.pagination.total || list.length,
                        pages: data.pagination.pages || 1,
                    };
                } else {
                    this.pagination.total = list.length;
                    this.pagination.pages = 1;
                }

                this.clearError("users");
                this.lastSyncedAt = new Date().toISOString();
            } catch (error) {
                console.error("Error loading users:", error);
                this.setError("Unable to load users", error.message || "Showing sample records instead.", "users");
                this.loadMockUsers();
            } finally {
                this.loadingUsers = false;
                this.filterUsers();
                this.syncSelectedUser();
            }
        },

        async loadOrganizations() {
            this.loadingOrganizations = true;
            this.clearError("organizations");

            try {
                const response = await fetch("/api/v1/admin/organizations", {
                    credentials: 'include',  // Include cookies for session auth
                    headers: this.authHeaders(),
                });

                if (!response.ok) {
                    if (response.status === 401 || response.status === 403) {
                        // Not authenticated - use mock data
                        this.loadMockOrganizations();
                        return;
                    }
                    const errorBody = await this.safeParse(response);
                    throw new Error(errorBody?.detail || "Failed to load organizations.");
                }

                const data = await this.safeParse(response);
                this.organizations = Array.isArray(data) ? data : [];
                this.clearError("organizations");
            } catch (error) {
                console.error("Error loading organizations:", error);
                this.setError("Unable to load organizations", error.message || "Showing sample organizations instead.", "organizations");
                this.loadMockOrganizations();
            } finally {
                this.loadingOrganizations = false;
                this.filterOrganizations();
                this.filterUsers();
                this.syncSelectedOrg();
            }
        },

        updateStats(data) {
            if (!data) return;

            this.stats = {
                totalUsers: data.users?.total ?? this.stats.totalUsers,
                adminUsers: data.users?.admin ?? this.stats.adminUsers,
                activeUsers: data.users?.active ?? this.stats.activeUsers,
                organizations: data.organizations?.total ?? this.stats.organizations,
            };

            this.lastSyncedAt = new Date().toISOString();
        },

        filterUsers() {
            const term = this.normalizeString(this.search);
            const organizationId = this.organizationFilter;

            let list = (this.users || []).slice();

            list = list.filter((user) => {
                const matchesSearch =
                    !term ||
                    this.normalizeString(user.username).includes(term) ||
                    this.normalizeString(user.email).includes(term) ||
                    this.normalizeString(user.full_name).includes(term) ||
                    this.normalizeString(user.organization_name).includes(term);

                const matchesRole = !this.roleFilter || user.role === this.roleFilter;

                const matchesStatus =
                    !this.statusFilter ||
                    (this.statusFilter === "active" && user.is_active) ||
                    (this.statusFilter === "inactive" && !user.is_active);

                const matchesOrganization =
                    !organizationId ||
                    String(user.organization_id || "") === organizationId ||
                    this.normalizeString(user.organization_name) === this.normalizeString(this.organizationLabel(organizationId));

                return matchesSearch && matchesRole && matchesStatus && matchesOrganization;
            });

            list = this.sortUsers(list);
            this.filteredUsers = list;
        },

        filterOrganizations() {
            const term = this.normalizeString(this.orgSearch);

            this.filteredOrganizations = (this.organizations || []).filter((org) => {
                return (
                    !term ||
                    this.normalizeString(org.name).includes(term) ||
                    this.normalizeString(org.type).includes(term) ||
                    this.normalizeString(org.email).includes(term)
                );
            });
        },

        sortUsers(list) {
            switch (this.sortBy) {
                case "name_asc":
                    return list.sort((a, b) => this.compareStrings(a.full_name || a.username, b.full_name || b.username));
                case "name_desc":
                    return list.sort((a, b) => this.compareStrings(b.full_name || b.username, a.full_name || a.username));
                case "role":
                    return list.sort((a, b) => this.compareStrings(a.role, b.role) || this.compareStrings(a.full_name || a.username, b.full_name || b.username));
                case "recent":
                default:
                    return list.sort((a, b) => {
                        const aTime = this.asTimestamp(a.last_login || a.created_at);
                        const bTime = this.asTimestamp(b.last_login || b.created_at);
                        return bTime - aTime;
                    });
            }
        },

        compareStrings(a, b) {
            return this.normalizeString(a).localeCompare(this.normalizeString(b));
        },

        normalizeString(value) {
            return (value || "").toString().trim().toLowerCase();
        },

        asTimestamp(value) {
            const date = new Date(value);
            const time = date.getTime();
            return Number.isNaN(time) ? 0 : time;
        },

        filteredRoles() {
            return this.roleDefinitions.filter((role) => !role.restricted || this.settings.isSuperAdmin);
        },

        roleLabel(value) {
            return this.roleDefinitions.find((role) => role.value === value)?.label || value || "User";
        },

        organizationLabel(id) {
            if (!id) return "Unassigned";
            const match = (this.organizations || []).find((org) => String(org.id) === String(id));
            return match?.name || "Unassigned";
        },

        formatOrganizationType(type) {
            if (!type) return "Organization";
            return type
                .toString()
                .split(/[\s_]+/)
                .filter(Boolean)
                .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
                .join(" ");
        },

        organizationFilterOptions() {
            return (this.organizations || [])
                .slice()
                .sort((a, b) => this.compareStrings(a.name, b.name))
                .map((org) => ({ value: String(org.id), label: org.name }));
        },

        activeFilters() {
            const filters = [];

            if (this.search) {
                filters.push({ key: "search", label: `Search: "${this.search}"` });
            }
            if (this.roleFilter) {
                filters.push({ key: "role", label: this.roleLabel(this.roleFilter) });
            }
            if (this.statusFilter) {
                filters.push({ key: "status", label: this.statusFilter === "active" ? "Active" : "Suspended" });
            }
            if (this.organizationFilter) {
                filters.push({ key: "organization", label: this.organizationLabel(this.organizationFilter) });
            }

            return filters;
        },

        hasActiveFilters() {
            return this.activeFilters().length > 0;
        },

        clearFilter(key) {
            switch (key) {
                case "search":
                    this.search = "";
                    break;
                case "role":
                    this.roleFilter = "";
                    break;
                case "status":
                    this.statusFilter = "";
                    break;
                case "organization":
                    this.organizationFilter = "";
                    break;
                default:
                    break;
            }
            this.filterUsers();
        },

        clearFilters() {
            this.search = "";
            this.roleFilter = "";
            this.statusFilter = "";
            this.organizationFilter = "";
            this.filterUsers();
        },

        lastSyncedLabel() {
            return this.formatRelative(this.lastSyncedAt);
        },

        openUserDetails(user) {
            this.selectedUser = { ...user };
            this.showViewUserModal = true;
        },

        closeUserDetails() {
            this.showViewUserModal = false;
            this.selectedUser = null;
        },

        openCreateUser() {
            this.resetNewUser();
            this.showAddUserModal = true;
        },

        openEditUser(user) {
            console.log('openEditUser called with user:', user);
            if (!this.canEditUser(user)) {
                console.log('Cannot edit user - permission denied');
                return;
            }
            this.selectedUser = { ...user };
            this.editUserForm = {
                id: user.id,
                username: user.username || "",
                email: user.email || "",
                full_name: user.full_name || "",
                role: user.role || this.newUser.role,
                organization_id: user.organization_id ? String(user.organization_id) : "",
                is_active: Boolean(user.is_active),
                password: "",
            };
            console.log('Opening edit modal with form:', this.editUserForm);
            this.showEditUserModal = true;
        },

        openCreateOrganization() {
            this.resetNewOrg();
            this.showAddOrgModal = true;
        },

        openOrganizationDetails(org) {
            this.openEditOrganization(org);
        },

        openEditOrganization(org) {
            if (!org) return;
            this.selectedOrg = { ...org };
            this.editOrgForm = {
                id: org.id,
                name: org.name || "",
                type: org.type || "hospital",
                email: org.email || "",
                contact: org.contact || "",
                is_active: org.is_active !== false,
            };
            this.showEditOrgModal = true;
        },

        canEditUser(user) {
            if (!this.settings.canManageUsers || !user) return false;
            // Super Admins can only be edited by other Super Admins
            if (user.role === "super_admin" && !this.settings.isSuperAdmin) return false;
            return true;
        },

        canEditUserByRole(form) {
            if (!form) return false;
            // Super Admin role can only be assigned/edited by Super Admins
            if (form.role === "super_admin" && !this.settings.isSuperAdmin) return false;
            return this.settings.canManageUsers;
        },

        canSuspendUser(user) {
            if (!this.canEditUser(user)) return false;
            // Super Admins cannot be suspended by anyone
            if (user.role === "super_admin") return false;
            return true;
        },

        canDeleteUser(user) {
            if (!this.canEditUser(user)) return false;
            // Cannot delete yourself
            if (user.id === this.settings.currentUserId) return false;
            // Super Admins cannot be deleted
            if (user.role === "super_admin") return false;
            return true;
        },
        
        canAssignUser(user) {
            // Only super admins and org admins can assign users
            if (!this.settings.isSuperAdmin && !this.settings.isOrgAdmin) return false;
            if (!user) return false;
            // Cannot assign super admins or admins
            if (user.role === "super_admin" || user.role === "admin") return false;
            return true;
        },
        
        healthcareStaff() {
            return this.users.filter(u => 
                ["doctor", "nurse", "counselor", "social_worker"].includes(u.role)
            );
        },
        
        openAssignModal(user) {
            this.selectedUserForAssignment = user;
            this.assignForm = {
                user_id: user.id,
                assigned_to_id: ""
            };
            this.showAssignModal = true;
        },
        
        async assignUser() {
            console.log('assignUser called with:', this.assignForm);
            if (!this.assignForm.assigned_to_id) {
                this.notify("Selection required", "Please select a staff member to assign", "warning");
                return;
            }
            
            const endpoint = `/admin/api/users/${this.assignForm.user_id}/assign`;
            console.log('Calling endpoint:', endpoint);
            
            try {
                const response = await fetch(endpoint, {
                    method: "POST",
                    headers: this.authHeaders({ "Content-Type": "application/json" }),
                    body: JSON.stringify({
                        assigned_to_id: parseInt(this.assignForm.assigned_to_id)
                    })
                });
                
                console.log('Response status:', response.status);
                
                if (!response.ok) {
                    const error = await this.safeParse(response);
                    console.error('API error:', error);
                    throw new Error(error.detail || "Failed to assign user");
                }
                
                // Success
                this.showAssignModal = false;
                await this.loadUsers();
                
                const staffMember = this.users.find(u => u.id === parseInt(this.assignForm.assigned_to_id));
                this.notify("User assigned", `Successfully assigned ${this.selectedUserForAssignment.username} to ${staffMember?.username || 'staff member'}`, "success");
            } catch (error) {
                console.error("Assignment error:", error);
                this.notify("Assignment failed", error.message || "Failed to assign user. Please try again.", "error");
            }
        },
        
        openOrgModal() {
            console.log('openOrgModal called - navigating to organizations page');
            // Navigate to organizations page
            window.location.href = '/admin/organizations';
        },

        async createUser() {
            try {
                if (!this.hasToken()) {
                    this.notify("Authentication required", "Please sign in to create users.", "warning");
                    return;
                }

                const payload = {
                    username: this.newUser.username.trim(),
                    email: this.newUser.email.trim(),
                    password: this.newUser.password,
                    full_name: this.newUser.full_name.trim(),
                    role: this.newUser.role,
                    organization_id: this.newUser.organization_id || null,
                    is_active: !!this.newUser.is_active,
                };

                if (!payload.password) {
                    this.notify("Missing password", "Please provide a password for the new user.", "warning");
                    return;
                }

                if (!this.settings.isSuperAdmin && payload.role === "super_admin") {
                    payload.role = "admin";
                }

                const response = await fetch("/api/v1/admin/users", {
                    method: "POST",
                    headers: this.authHeaders({ "Content-Type": "application/json" }),
                    body: JSON.stringify(payload),
                });

                if (response.ok) {
                    this.notify("User created", `${payload.username} has been added.`, "success");
                    this.showAddUserModal = false;
                    this.resetNewUser();
                    await this.loadUsers();
                    await this.loadStats();
                } else {
                    const error = await this.safeParse(response);
                    this.notify("Create failed", error.detail || "Unable to create user.", "error");
                }
            } catch (error) {
                console.error("Error creating user:", error);
                this.notify("Error", "Unexpected error creating user.", "error");
            }
        },

        async updateUser() {
            if (!this.editUserForm.id) return;
            if (!this.canEditUserByRole(this.editUserForm)) {
                this.notify("Insufficient permissions", "You do not have permission to update this user.", "error");
                return;
            }

            const payload = {
                username: this.editUserForm.username.trim(),
                email: this.editUserForm.email.trim(),
                full_name: this.editUserForm.full_name.trim(),
                role: this.editUserForm.role,
                organization_id: this.editUserForm.organization_id || null,
                is_active: !!this.editUserForm.is_active,
            };

            if (this.editUserForm.password) {
                payload.password = this.editUserForm.password;
            }

            const success = await this.submitUserUpdate(this.editUserForm.id, payload, "User updated");
            if (success) {
                this.showEditUserModal = false;
                this.editUserForm.password = "";
                await this.loadUsers();
                await this.loadStats();
            }
        },

        async submitUserUpdate(userId, payload, successMessage = "Changes saved") {
            try {
                if (!this.hasToken()) {
                    this.notify("Authentication required", "Please sign in to manage users.", "warning");
                    return false;
                }

                const response = await fetch(`/api/v1/admin/users/${userId}`, {
                    method: "PUT",
                    headers: this.authHeaders({ "Content-Type": "application/json" }),
                    body: JSON.stringify(payload),
                });

                if (response.ok) {
                    this.notify("Success", successMessage, "success");
                    return true;
                }

                const error = await this.safeParse(response);
                this.notify("Update failed", error.detail || "Unable to update user.", "error");
                return false;
            } catch (error) {
                console.error("Error updating user:", error);
                this.notify("Error", "Unexpected error updating user.", "error");
                return false;
            }
        },

        async toggleUserStatus(user) {
            if (!this.canSuspendUser(user)) {
                this.notify("Permission denied", "Super Admins cannot be suspended.", "error");
                return;
            }
            const nextStatus = !user.is_active;
            const success = await this.submitUserUpdate(
                user.id,
                { is_active: nextStatus },
                nextStatus ? "User reactivated" : "User suspended"
            );
            if (success) {
                await this.loadUsers();
            }
        },

        async deleteUser(user) {
            if (!this.canDeleteUser(user)) {
                if (user.role === "super_admin") {
                    this.notify("Permission denied", "Super Admins cannot be deleted.", "error");
                }
                return;
            }
            if (!confirm(`Remove ${user.username}? This action cannot be undone.`)) {
                return;
            }

            try {
                const response = await fetch(`/api/v1/admin/users/${user.id}`, {
                    method: "DELETE",
                    headers: this.authHeaders(),
                });

                if (response.ok) {
                    this.notify("User removed", `${user.username} has been deleted.`, "success");
                    if (this.showViewUserModal) {
                        this.closeUserDetails();
                    }
                    await this.loadUsers();
                    await this.loadStats();
                } else {
                    const error = await this.safeParse(response);
                    this.notify("Deletion failed", error.detail || "Unable to delete user.", "error");
                }
            } catch (error) {
                console.error("Error deleting user:", error);
                this.notify("Error", "Unexpected error deleting user.", "error");
            }
        },

        resetNewUser() {
            this.newUser = {
                username: "",
                email: "",
                password: "",
                full_name: "",
                role: this.settings.isSuperAdmin ? "admin" : "user",
                organization_id: "",
                is_active: true,
            };
        },

        async createOrganization() {
            try {
                if (!this.hasToken()) {
                    this.notify("Authentication required", "Please sign in to create organizations.", "warning");
                    return;
                }

                const payload = {
                    name: this.newOrg.name.trim(),
                    type: this.newOrg.type,
                    email: this.newOrg.email.trim(),
                    contact: this.newOrg.contact.trim(),
                    is_active: !!this.newOrg.is_active,
                };

                const response = await fetch("/api/v1/admin/organizations", {
                    method: "POST",
                    headers: this.authHeaders({ "Content-Type": "application/json" }),
                    body: JSON.stringify(payload),
                });

                if (response.ok) {
                    this.notify("Organization created", `${payload.name} has been registered.`, "success");
                    this.showAddOrgModal = false;
                    this.resetNewOrg();
                    await this.loadOrganizations();
                    await this.loadStats();
                } else {
                    const error = await this.safeParse(response);
                    this.notify("Create failed", error.detail || "Unable to create organization.", "error");
                }
            } catch (error) {
                console.error("Error creating organization:", error);
                this.notify("Error", "Unexpected error creating organization.", "error");
            }
        },

        resetNewOrg() {
            this.newOrg = {
                name: "",
                type: "hospital",
                email: "",
                contact: "",
                is_active: true,
            };
        },

        async updateOrganization() {
            if (!this.editOrgForm.id) {
                this.showEditOrgModal = false;
                return;
            }

            try {
                if (!this.hasToken()) {
                    this.notify("Authentication required", "Please sign in to manage organizations.", "warning");
                    return;
                }

                const payload = {
                    name: this.editOrgForm.name.trim(),
                    type: this.editOrgForm.type,
                    email: this.editOrgForm.email?.trim() || null,
                    contact: this.editOrgForm.contact?.trim() || null,
                    is_active: !!this.editOrgForm.is_active,
                };

                const response = await fetch(`/api/v1/admin/organizations/${this.editOrgForm.id}`, {
                    method: "PUT",
                    headers: this.authHeaders({ "Content-Type": "application/json" }),
                    body: JSON.stringify(payload),
                });

                if (response.ok) {
                    this.notify("Organization updated", "Changes saved successfully.", "success");
                    this.showEditOrgModal = false;
                    await this.loadOrganizations();
                } else {
                    const error = await this.safeParse(response);
                    this.notify("Update failed", error.detail || "Unable to update organization (endpoint may be unavailable).", "warning");
                }
            } catch (error) {
                console.error("Error updating organization:", error);
                this.notify("Error", "Unexpected error updating organization.", "error");
            }
        },

        async deleteOrganization(org) {
            if (!org) return;
            if (!confirm(`Remove ${org.name}? This action cannot be undone.`)) {
                return;
            }

            try {
                if (!this.hasToken()) {
                    this.notify("Authentication required", "Please sign in to manage organizations.", "warning");
                    return;
                }

                const response = await fetch(`/api/v1/admin/organizations/${org.id}`, {
                    method: "DELETE",
                    headers: this.authHeaders(),
                });

                if (response.ok) {
                    this.notify("Organization removed", `${org.name} has been deleted.`, "success");
                    if (this.showEditOrgModal && this.editOrgForm.id === org.id) {
                        this.showEditOrgModal = false;
                    }
                    await this.loadOrganizations();
                    await this.loadStats();
                } else {
                    const error = await this.safeParse(response);
                    this.notify("Deletion failed", error.detail || "Unable to delete organization.", "error");
                }
            } catch (error) {
                console.error("Error deleting organization:", error);
                this.notify("Error", "Unexpected error deleting organization.", "error");
            }
        },

        syncSelectedUser() {
            if (!this.selectedUser) return;
            const latest = (this.users || []).find((user) => user.id === this.selectedUser.id);
            if (latest) {
                this.selectedUser = { ...latest };
            } else {
                this.closeUserDetails();
            }
        },

        syncSelectedOrg() {
            if (!this.selectedOrg) return;
            const latest = (this.organizations || []).find((org) => org.id === this.selectedOrg.id);
            if (latest) {
                this.selectedOrg = { ...latest };
            } else {
                this.selectedOrg = null;
            }
        },

        // Formatting helpers
        formatDate(value) {
            if (!value) return "—";
            const date = new Date(value);
            if (Number.isNaN(date.getTime())) return value;
            return date.toLocaleString();
        },

        formatRelative(value) {
            if (!value) return "Never";
            const date = new Date(value);
            if (Number.isNaN(date.getTime())) return value;

            const diffMs = Date.now() - date.getTime();
            const seconds = Math.floor(diffMs / 1000);
            const minutes = Math.floor(seconds / 60);
            const hours = Math.floor(minutes / 60);
            const days = Math.floor(hours / 24);

            if (days > 0) return `${days}d ago`;
            if (hours > 0) return `${hours}h ago`;
            if (minutes > 0) return `${minutes}m ago`;
            if (seconds > 5) return `${seconds}s ago`;
            return "Just now";
        },

        // Mock fallbacks
        loadMockStats() {
            this.stats = {
                totalUsers: 25,
                adminUsers: 4,
                activeUsers: 18,
                organizations: 4,
            };
        },

        loadMockUsers() {
            this.users = [
                {
                    id: 1,
                    username: "admin",
                    email: "admin@healthcare.ai",
                    full_name: "Healthcare Admin",
                    role: "super_admin",
                    is_active: true,
                    organization_name: "Healthcare AI Platform",
                    organization_id: 1,
                    created_at: new Date().toISOString(),
                    last_login: new Date().toISOString(),
                },
                {
                    id: 2,
                    username: "dr.wong",
                    email: "wong@hospital.hk",
                    full_name: "Dr. Apple Wong",
                    role: "doctor",
                    is_active: true,
                    organization_name: "General Hospital",
                    created_at: new Date().toISOString(),
                    last_login: new Date(Date.now() - 3600 * 1000).toISOString(),
                },
                {
                    id: 3,
                    username: "nurse.chan",
                    email: "chan@clinic.hk",
                    full_name: "Nurse Chan",
                    role: "nurse",
                    is_active: false,
                    organization_name: "Community Health Center",
                    created_at: new Date().toISOString(),
                    last_login: null,
                },
            ];
            this.pagination.total = this.users.length;
            this.pagination.pages = 1;
            this.filteredUsers = this.sortUsers(this.users.slice());
            this.lastSyncedAt = null;
        },

        loadMockOrganizations() {
            this.organizations = [
                {
                    id: 1,
                    name: "Healthcare AI Platform",
                    type: "platform",
                    email: "admin@healthcare.ai",
                    contact: "Aida Lam",
                    is_active: true,
                    user_count: 10,
                },
                {
                    id: 2,
                    name: "General Hospital",
                    type: "hospital",
                    email: "admin@general-hospital.hk",
                    contact: "Operations Desk",
                    is_active: true,
                    user_count: 6,
                },
                {
                    id: 3,
                    name: "Community Health Center",
                    type: "clinic",
                    email: "info@chc.hk",
                    contact: "Patient Services",
                    is_active: true,
                    user_count: 3,
                },
            ];
            this.filteredOrganizations = this.organizations;
        },
    };
}

let userManagementComponentRegistered = false;

function registerUserManagementComponent() {
    if (typeof Alpine === "undefined") {
        return false;
    }

    if (userManagementComponentRegistered) {
        return true;
    }

    userManagementComponentRegistered = true;
    Alpine.data("userManagementPage", (config = {}) => userManagementPage(config));
    return true;
}

if (typeof Alpine !== "undefined") {
    registerUserManagementComponent();
} else if (typeof document !== "undefined") {
    document.addEventListener("alpine:init", () => {
        registerUserManagementComponent();
    });
}

if (typeof window !== "undefined") {
    window.userManagementPage = userManagementPage;
}
