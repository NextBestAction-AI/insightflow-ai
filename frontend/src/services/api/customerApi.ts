import { apiClient } from "./apiClient";

export interface Customer {
  id: number;
  name: string;
  email: string;
  company: string;
  industry?: string;
  account_type?: string;
  region?: string;
  annual_revenue_usd?: number;
  employee_count?: number;
}

export const customerApi = {
  getCustomers: async (skip = 0, limit = 100): Promise<{ total: number; items: Customer[] }> => {
    const res = await apiClient.get<{ total: number; items: Customer[] }>(`/customers?skip=${skip}&limit=${limit}`);
    return res.data;
  },

  getCustomer: async (id: number): Promise<Customer> => {
    const res = await apiClient.get<Customer>(`/customers/${id}`);
    return res.data;
  },

  createCustomer: async (data: Partial<Customer>): Promise<Customer> => {
    const res = await apiClient.post<Customer>("/customers", data);
    return res.data;
  },
};
