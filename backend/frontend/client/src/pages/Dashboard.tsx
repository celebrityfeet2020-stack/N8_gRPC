import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { deviceApi, Device } from "@/lib/api";
import { Server, Activity, AlertTriangle, Cpu } from "lucide-react";
import { Link } from "wouter";

export default function Dashboard() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDevices = async () => {
      try {
        const data = await deviceApi.list();
        setDevices(data);
      } catch (error) {
        console.error("Failed to fetch devices", error);
      } finally {
        setLoading(false);
      }
    };

    fetchDevices();
    // 每30秒刷新一次
    const interval = setInterval(fetchDevices, 30000);
    return () => clearInterval(interval);
  }, []);

  const onlineCount = devices.filter(d => d.status === 'online').length;
  const offlineCount = devices.length - onlineCount;
  const avgCpu = devices.length > 0 
    ? (devices.reduce((acc, d) => acc + d.cpu_usage, 0) / devices.length).toFixed(1) 
    : 0;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">概览</h1>
        <p className="text-muted-foreground mt-2">系统运行状态和关键指标监控</p>
      </div>

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">总设备数</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{devices.length}</div>
            <p className="text-xs text-muted-foreground">已注册设备总量</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">在线设备</CardTitle>
            <Activity className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">{onlineCount}</div>
            <p className="text-xs text-muted-foreground">实时在线</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">离线设备</CardTitle>
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-500">{offlineCount}</div>
            <p className="text-xs text-muted-foreground">需关注</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">平均CPU负载</CardTitle>
            <Cpu className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{avgCpu}%</div>
            <p className="text-xs text-muted-foreground">所有在线设备平均值</p>
          </CardContent>
        </Card>
      </div>

      {/* 最近活跃设备 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>设备状态概览</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {devices.slice(0, 5).map(device => (
                <div key={device.id} className="flex items-center justify-between p-4 border rounded-lg bg-card/50">
                  <div className="flex items-center space-x-4">
                    <div className={`w-3 h-3 rounded-full ${device.status === 'online' ? 'bg-green-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-gray-500'}`} />
                    <div>
                      <p className="font-medium">{device.hostname}</p>
                      <p className="text-xs text-muted-foreground font-mono">{device.device_id}</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-6 text-sm text-muted-foreground">
                    <div className="flex items-center">
                      <Cpu className="h-3 w-3 mr-1" />
                      {device.cpu_usage.toFixed(1)}%
                    </div>
                    <div className="hidden sm:block">
                      {new Date(device.last_seen_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
              
              {devices.length === 0 && !loading && (
                <div className="text-center py-8 text-muted-foreground">
                  暂无设备连接
                </div>
              )}
              
              {devices.length > 5 && (
                <div className="text-center pt-2">
                  <Link href="/devices">
                    <a className="text-sm text-primary hover:underline">查看所有设备 &rarr;</a>
                  </Link>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>快速操作</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground mb-4">
                常用管理命令快捷入口
              </p>
              {/* 这里可以放置一些快捷操作按钮，后续开发 */}
              <div className="p-4 border border-dashed rounded-lg text-center text-sm text-muted-foreground">
                选择设备后可执行命令
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
