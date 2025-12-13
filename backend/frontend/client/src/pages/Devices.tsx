import { useEffect, useState } from "react";
import { deviceApi, Device } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { 
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Search, Terminal, RefreshCw, Power } from "lucide-react";
import { toast } from "sonner";

export default function Devices() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [command, setCommand] = useState("");
  const [executing, setExecuting] = useState(false);
  const [commandResult, setCommandResult] = useState<string | null>(null);

  const fetchDevices = async () => {
    setLoading(true);
    try {
      const data = await deviceApi.list();
      setDevices(data);
    } catch (error) {
      toast.error("获取设备列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
  }, []);

  const handleExecute = async () => {
    if (!selectedDevice || !command.trim()) return;
    
    setExecuting(true);
    setCommandResult(null);
    
    try {
      const result = await deviceApi.execute(selectedDevice.device_id, command);
      toast.success("命令已发送");
      
      // 轮询结果
      let attempts = 0;
      const pollInterval = setInterval(async () => {
        attempts++;
        try {
          const cmdData = await deviceApi.getCommand(result.command_id);
          if (cmdData.status === 'completed' || cmdData.status === 'failed') {
            clearInterval(pollInterval);
            setCommandResult(cmdData.stdout || cmdData.stderr || "无输出");
            setExecuting(false);
            if (cmdData.status === 'failed') {
              toast.error("命令执行失败");
            } else {
              toast.success("命令执行完成");
            }
          }
        } catch (e) {
          // ignore
        }
        
        if (attempts > 20) { // 20次尝试后超时 (约40秒)
          clearInterval(pollInterval);
          setExecuting(false);
          toast.error("获取结果超时");
        }
      }, 2000);
      
    } catch (error) {
      toast.error("命令发送失败");
      setExecuting(false);
    }
  };

  const filteredDevices = devices.filter(d => 
    d.hostname.toLowerCase().includes(searchTerm.toLowerCase()) ||
    d.device_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    d.os_type.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">设备管理</h1>
          <p className="text-muted-foreground mt-2">查看和管理所有已注册设备</p>
        </div>
        <Button onClick={fetchDevices} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          刷新
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center space-x-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input 
              placeholder="搜索设备 (主机名, ID, OS)..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="max-w-sm"
            />
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>状态</TableHead>
                <TableHead>主机名</TableHead>
                <TableHead>设备ID</TableHead>
                <TableHead>系统</TableHead>
                <TableHead>CPU</TableHead>
                <TableHead>内存</TableHead>
                <TableHead>最后在线</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredDevices.map((device) => (
                <TableRow key={device.id}>
                  <TableCell>
                    <div className={`flex items-center ${device.status === 'online' ? 'text-green-500' : 'text-gray-500'}`}>
                      <div className={`w-2 h-2 rounded-full mr-2 ${device.status === 'online' ? 'bg-green-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-gray-500'}`} />
                      {device.status === 'online' ? '在线' : '离线'}
                    </div>
                  </TableCell>
                  <TableCell className="font-medium">{device.hostname}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{device.device_id}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{device.os_type}</Badge>
                  </TableCell>
                  <TableCell>{device.cpu_usage.toFixed(1)}%</TableCell>
                  <TableCell>{device.memory_usage.toFixed(1)}%</TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {new Date(device.last_seen_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Dialog>
                      <DialogTrigger asChild>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => {
                            setSelectedDevice(device);
                            setCommandResult(null);
                            setCommand("");
                          }}
                          disabled={device.status !== 'online'}
                        >
                          <Terminal className="h-4 w-4 mr-2" />
                          终端
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="sm:max-w-[600px]">
                        <DialogHeader>
                          <DialogTitle>远程终端 - {device.hostname}</DialogTitle>
                          <DialogDescription>
                            在设备 {device.device_id} 上执行Shell命令
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                          <div className="space-y-2">
                            <Input
                              placeholder="输入命令 (例如: uptime, df -h)..."
                              value={command}
                              onChange={(e) => setCommand(e.target.value)}
                              onKeyDown={(e) => e.key === 'Enter' && handleExecute()}
                              className="font-mono"
                            />
                            <div className="flex space-x-2">
                              <Button 
                                onClick={handleExecute} 
                                disabled={executing || !command.trim()}
                                className="w-full"
                              >
                                {executing ? "执行中..." : "发送命令"}
                              </Button>
                            </div>
                          </div>
                          
                          <div className="bg-black/90 text-green-400 p-4 rounded-md font-mono text-sm min-h-[200px] max-h-[400px] overflow-y-auto whitespace-pre-wrap">
                            {commandResult || (executing ? "等待响应..." : "> 等待输入命令...")}
                          </div>
                        </div>
                      </DialogContent>
                    </Dialog>
                  </TableCell>
                </TableRow>
              ))}
              {filteredDevices.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                    未找到匹配的设备
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
