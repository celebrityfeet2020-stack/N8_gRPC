import { useState, useEffect } from "react";
import { Link, useLocation } from "wouter";
import { 
  LayoutDashboard, 
  Server, 
  Terminal, 
  Users, 
  Settings, 
  LogOut, 
  Menu, 
  X,
  Shield
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { userApi, User } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const [location, setLocation] = useLocation();
  const [user, setUser] = useState<User | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  useEffect(() => {
    // 获取当前用户信息
    userApi.me().catch(() => {
      // 如果获取失败，重定向到登录页
      setLocation("/login");
    });
  }, [setLocation]);

  const handleLogout = () => {
    localStorage.removeItem("n8_api_key");
    setLocation("/login");
  };

  const navItems = [
    { href: "/", icon: LayoutDashboard, label: "概览" },
    { href: "/devices", icon: Server, label: "设备管理" },
    { href: "/commands", icon: Terminal, label: "命令历史" },
    { href: "/users", icon: Users, label: "用户管理", adminOnly: true },
    { href: "/settings", icon: Settings, label: "系统设置" },
  ];

  return (
    <div className="min-h-screen bg-background flex">
      {/* 移动端遮罩 */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* 侧边栏 */}
      <aside 
        className={cn(
          "fixed lg:static inset-y-0 left-0 z-50 w-64 bg-sidebar border-r border-sidebar-border transform transition-transform duration-200 ease-in-out lg:transform-none flex flex-col",
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="h-16 flex items-center px-6 border-b border-sidebar-border">
          <Terminal className="h-6 w-6 text-primary mr-2" />
          <span className="font-bold text-lg tracking-tight">N8 Control</span>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href}>
              <a 
                className={cn(
                  "flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors",
                  location === item.href 
                    ? "bg-sidebar-accent text-sidebar-accent-foreground" 
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                )}
                onClick={() => setIsSidebarOpen(false)}
              >
                <item.icon className="h-4 w-4 mr-3" />
                {item.label}
              </a>
            </Link>
          ))}
        </nav>

        <div className="p-4 border-t border-sidebar-border">
          <div className="flex items-center mb-4 px-2">
            <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold mr-3">
              {user?.display_name?.[0] || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.display_name || "加载中..."}</p>
              <div className="flex items-center text-xs text-muted-foreground">
                <Shield className="h-3 w-3 mr-1" />
                {user?.role || "VIEWER"}
              </div>
            </div>
          </div>
          <Button 
            variant="outline" 
            className="w-full justify-start text-muted-foreground hover:text-foreground"
            onClick={handleLogout}
          >
            <LogOut className="h-4 w-4 mr-2" />
            退出登录
          </Button>
        </div>
      </aside>

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部导航栏 (移动端) */}
        <header className="h-16 lg:hidden flex items-center px-4 border-b border-border bg-background">
          <Button variant="ghost" size="icon" onClick={() => setIsSidebarOpen(true)}>
            <Menu className="h-6 w-6" />
          </Button>
          <span className="ml-4 font-bold">N8设备控制中心</span>
        </header>

        {/* 页面内容 */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-8">
          <div className="container max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
