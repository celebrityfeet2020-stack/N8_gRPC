import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Devices from "./pages/Devices";

// 简单的占位组件，后续开发
const Commands = () => <div className="p-4">命令历史 (开发中)</div>;
const Users = () => <div className="p-4">用户管理 (开发中)</div>;
const Settings = () => <div className="p-4">系统设置 (开发中)</div>;

function Router() {
  return (
    <Switch>
      <Route path="/login" component={Login} />
      
      {/* 需要Layout包裹的路由 */}
      <Route path="/">
        <Layout>
          <Dashboard />
        </Layout>
      </Route>
      <Route path="/devices">
        <Layout>
          <Devices />
        </Layout>
      </Route>
      <Route path="/commands">
        <Layout>
          <Commands />
        </Layout>
      </Route>
      <Route path="/users">
        <Layout>
          <Users />
        </Layout>
      </Route>
      <Route path="/settings">
        <Layout>
          <Settings />
        </Layout>
      </Route>

      <Route path="/404" component={NotFound} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="dark">
        <TooltipProvider>
          <Toaster position="top-right" />
          <Router />
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
