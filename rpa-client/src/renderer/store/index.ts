/**
 * Redux Store 配置
 */
import { configureStore } from '@reduxjs/toolkit';
import flowReducer from './flowSlice';
import executionReducer from './executionSlice';

export const store = configureStore({
  reducer: {
    flow: flowReducer,
    execution: executionReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
