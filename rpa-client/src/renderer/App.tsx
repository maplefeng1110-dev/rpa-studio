/**
 * App 主组件
 */
import React from 'react';
import { Provider } from 'react-redux';
import { store } from './store';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { FlowEditor } from './components/editor/FlowEditor';
import { PropertiesPanel } from './components/properties/PropertiesPanel';
import { ExecutionLog } from './components/execution/ExecutionLog';
import { useExecution } from './hooks/useExecution';

const AppContent: React.FC = () => {
  const { status } = useExecution();

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      <Header />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 flex overflow-hidden">
            <div className="flex-1 overflow-hidden">
              <FlowEditor />
            </div>
            <div className="w-80 border-l border-gray-200 overflow-hidden">
              <PropertiesPanel />
            </div>
          </div>
          {status !== 'idle' && (
            <div className="h-64 border-t border-gray-200 overflow-hidden">
              <ExecutionLog />
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <Provider store={store}>
      <AppContent />
    </Provider>
  );
};
