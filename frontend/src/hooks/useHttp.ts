import axios from 'axios';
import type { AxiosRequestConfig } from 'axios';
import { useStore } from './store';
import { fetchAuthSession } from 'aws-amplify/auth';

const api = axios.create({
  baseURL: String(import.meta.env.VITE_APP_BASEURL)
});

// 認証実装を有効化
api.interceptors.request.use(async (config) => {
  try {
    const token = (await fetchAuthSession()).tokens?.idToken?.toString();
    if (token) {
      config.headers.Authorization = 'Bearer ' + token;
    }
  } catch (error) {
    console.error('認証トークンの取得に失敗しました:', error);
  }
  return config;
});

const useHttp = () => {
  const { startLoading, endLoading } = useStore();

  const get = async <T>(url: string, config?: AxiosRequestConfig) => {
    try {
      startLoading();
      const response = await api.get<T>(url, config);
      return response.data;
    } catch (e) {
      throw e;
    } finally {
      endLoading();
    }
  };

  const post = async <T>(url: string, data?: any, config?: AxiosRequestConfig) => {
    try {
      startLoading();
      const response = await api.post<T>(url, data, config);
      return response.data;
    } catch (e) {
      throw e;
    } finally {
      endLoading();
    }
  };

  const put = async <T>(url: string, data?: any, config?: AxiosRequestConfig) => {
    try {
      startLoading();
      const response = await api.put<T>(url, data, config);
      return response.data;
    } catch (e) {
      throw e;
    } finally {
      endLoading();
    }
  };

  const del = async <T>(url: string, config?: AxiosRequestConfig) => {
    try {
      startLoading();
      const response = await api.delete<T>(url, config);
      return response.data;
    } catch (e) {
      throw e;
    } finally {
      endLoading();
    }
  };

  return { get, post, put, delete: del };
};

export default useHttp;
