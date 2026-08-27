import { apiClient } from "./client";
import type { SingleSettingResponse, SystemSettings, SystemSettingsResponse } from "../../types/api";

export const settingsApi = {
  getSettings: async (): Promise<SystemSettingsResponse> => {
    const response = await apiClient.get<SystemSettingsResponse>("/settings");
    return response.data;
  },

  updateSettings: async (settings: Partial<SystemSettings>): Promise<SystemSettingsResponse> => {
    const response = await apiClient.put<SystemSettingsResponse>("/settings", { settings });
    return response.data;
  },

  updateSingleSetting: async (key: string, value: any): Promise<SingleSettingResponse> => {
    const response = await apiClient.put<SingleSettingResponse>(`/settings/${encodeURIComponent(key)}`, { value });
    return response.data;
  },

  resetSettings: async (keys?: string[]): Promise<SystemSettingsResponse> => {
    const response = await apiClient.post<SystemSettingsResponse>("/settings/reset", { keys });
    return response.data;
  },
};
