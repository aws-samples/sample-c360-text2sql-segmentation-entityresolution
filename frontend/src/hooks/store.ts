import { create } from 'zustand';

interface StoreState {
  loadingCounter: number;
  loading: boolean;
  showError: boolean;
  startLoading: () => void;
  endLoading: () => void;
  setShowError: (show: boolean) => void;
}

export const useStore = create<StoreState>((set) => ({
  loadingCounter: 0,
  loading: false,
  showError: false,
  startLoading: () =>
    set((state) => ({
      loadingCounter: state.loadingCounter + 1,
      loading: true
    })),
  endLoading: () =>
    set((state) => {
      const newCounter = Math.max(0, state.loadingCounter - 1);
      return {
        loadingCounter: newCounter,
        loading: newCounter > 0
      };
    }),
  setShowError: (show) => set({ showError: show })
}));
