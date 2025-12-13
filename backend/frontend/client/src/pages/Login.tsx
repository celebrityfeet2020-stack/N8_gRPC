import { useState } from "react";
import { useLocation } from "wouter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { userApi } from "@/lib/api";
import { ShieldCheck, Terminal } from "lucide-react";

export default function Login() {
  const [apiKey, setApiKey] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [, setLocation] = useLocation();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!apiKey.trim()) {
      toast.error("请输入API Key");
      return;
    }

    if (!apiKey.startsWith("sk-")) {
      toast.error("无效的API Key格式 (应以 sk- 开头)");
      return;
    }

    setIsLoading(true);

    try {
      // 临时保存以便验证
      localStorage.setItem("n8_api_key", apiKey);
      
      // 验证API Key是否有效
      const user = await userApi.me();
      
      toast.success(`欢迎回来, ${user.display_name}`);
      setLocation("/");
    } catch (error) {
      console.error(error);
      localStorage.removeItem("n8_api_key");
      toast.error("登录失败: API Key无效或已过期");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="h-12 w-12 bg-primary/10 rounded-lg flex items-center justify-center">
              <Terminal className="h-8 w-8 text-primary" />
            </div>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">N8设备控制中心</h1>
          <p className="text-muted-foreground">请输入您的API Key以继续</p>
        </div>

        <Card className="border-border/50 shadow-lg">
          <CardHeader>
            <CardTitle>身份验证</CardTitle>
            <CardDescription>
              使用管理员分发的API Key登录系统
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleLogin}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="apiKey">API Key</Label>
                <div className="relative">
                  <ShieldCheck className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="apiKey"
                    placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    className="pl-9 font-mono"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    autoComplete="off"
                  />
                </div>
              </div>
            </CardContent>
            <CardFooter>
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? "验证中..." : "登录"}
              </Button>
            </CardFooter>
          </form>
        </Card>
        
        <div className="text-center text-sm text-muted-foreground">
          <p>仅限授权人员访问 | 所有操作将被审计</p>
        </div>
      </div>
    </div>
  );
}
