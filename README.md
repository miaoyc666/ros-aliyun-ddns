# ROS Aliyun DDNS

一个自建 DDNS 中转服务，用于让 RouterOS 或其他路由器通过 HTTP 请求更新阿里云云解析 DNS 的 A 记录。

路由器只需要保存本服务的访问令牌，不需要保存阿里云 AccessKey。阿里云密钥只配置在运行该服务的服务器环境变量里。

这个项目的设计初衷是给 RouterOS 脚本请求使用。为了让 RouterOS 的 `/tool fetch` 更容易拼接和调用，接口参数都设计在 URL query params 中，例如 `token`、`domain` 和 `ip`。

## 功能

- 接收路由器发来的 DDNS 更新请求
- 校验自定义访问令牌，避免接口被随意调用
- 调用阿里云云解析 API 查询指定域名的 A 记录
- 如果记录存在则更新 IP，如果不存在则创建记录
- 支持显式传入 IP，也支持使用请求来源 IP

## 技术栈

- Python 3
- Flask
- Gunicorn
- Alibaba Cloud DNS SDK

## 环境变量

复制 `.env.example` 并按实际值配置：

```bash
cp .env.example .env
```

需要的变量如下：

```env
DDNS_PROXY_TOKEN=change-me-to-a-random-string
ALIYUN_ACCESS_KEY_ID=your-access-key-id
ALIYUN_ACCESS_KEY_SECRET=your-access-key-secret
```

说明：

- `DDNS_PROXY_TOKEN`：本服务的调用令牌，路由器请求时需要带上。
- `ALIYUN_ACCESS_KEY_ID`：阿里云 AccessKey ID。
- `ALIYUN_ACCESS_KEY_SECRET`：阿里云 AccessKey Secret。

建议给阿里云 RAM 用户只授予云解析 DNS 所需的最小权限。

## 安装

推荐使用 Makefile 初始化项目：

```bash
make init
```

该命令会创建 `.env`、初始化 `.venv`、升级 pip 相关工具，并安装依赖。

也可以手动执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## 本地运行

先编辑 `.env`，填入真实配置：

```env
DDNS_PROXY_TOKEN=your-random-token
ALIYUN_ACCESS_KEY_ID=your-access-key-id
ALIYUN_ACCESS_KEY_SECRET=your-access-key-secret
```

启动服务：

```bash
make run
```

`make run` 会执行：

```bash
set -a; source .env; set +a; .venv/bin/python3 app.py
```

默认监听：

```text
0.0.0.0:6180
```

## 生产运行

可以直接使用 Gunicorn 前台运行：

```bash
make gunicorn
```

更推荐在服务器上用 supervisord 作为守护进程运行，保证服务异常退出后能自动拉起。

### 使用 supervisord

示例配置在 `deploy/supervisor/ros-aliyun-ddns.conf.example`。

先安装服务器依赖：

```bash
sudo apt update
sudo apt install -y python3 python3-venv make supervisor
```

假设项目部署在 `/opt/ros-aliyun-ddns`：

```bash
cd /opt/ros-aliyun-ddns
make init
vim .env
```

确认 `.env` 已填好后，创建日志目录并复制 supervisor 配置：

```bash
sudo mkdir -p /var/log/ros-aliyun-ddns
sudo chown www-data:www-data /var/log/ros-aliyun-ddns
sudo cp deploy/supervisor/ros-aliyun-ddns.conf.example /etc/supervisor/conf.d/ros-aliyun-ddns.conf
```

根据实际部署路径和运行用户编辑配置：

```bash
sudo vim /etc/supervisor/conf.d/ros-aliyun-ddns.conf
```

至少确认这些字段正确：

```ini
directory=/opt/ros-aliyun-ddns
command=/usr/bin/make gunicorn
user=www-data
stdout_logfile=/var/log/ros-aliyun-ddns/supervisor.log
```

如果你把 `user` 改成其他用户，也要同步调整 `/var/log/ros-aliyun-ddns` 的目录 owner。

加载并启动服务：

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start ros-aliyun-ddns
```

查看状态和日志：

```bash
sudo supervisorctl status ros-aliyun-ddns
sudo tail -f /var/log/ros-aliyun-ddns/supervisor.log
```

如果放在公网，建议在前面加反向代理并启用 HTTPS，例如 Nginx、Caddy 或 Traefik。

## 接口

接口使用 `GET` 请求，并通过 query params 传递参数。这是为了适配 RouterOS 脚本场景，避免在路由器侧构造请求体或复杂 header。

### 更新指定域名

```http
GET /ddns?token=<token>&domain=<fqdn>&ip=<ipv4>
```

示例：

```bash
curl "http://127.0.0.1:6180/ddns?token=your-random-token&domain=proxy.example.com&ip=1.2.3.4"
```

响应示例：

```json
{
  "status": "finished",
  "data": "updated proxy.example.com -> 1.2.3.4"
}
```

### 使用请求来源 IP

如果不传 `ip` 参数，服务会使用请求来源 IP：

```bash
curl "http://127.0.0.1:6180/ddns?token=your-random-token&domain=proxy.example.com"
```

注意：如果服务部署在反向代理后面，`request.remote_addr` 可能是代理服务器 IP，而不是路由器公网 IP。此时建议由路由器显式传入 `ip` 参数，或者在代码中补充可信代理头处理。

## 域名拆分规则

服务会把传入的完整域名拆成主机记录和主域名：

```text
proxy.example.com -> RR=proxy, Domain=example.com
example.com       -> RR=@,     Domain=example.com
```

当前实现按最后两段作为主域名处理，适合 `example.com` 这类域名。对于 `example.com.cn`、`example.co.uk` 等多级公共后缀域名，需要按实际情况调整 `split_domain` 逻辑。

## RouterOS 使用 DDNS

在 RouterOS 添加一个脚本，执行后将公网 IP 解析到指定域名。

### 配置脚本

进入 `[System]` -> `[Scripts]` -> `[+]`，新增脚本并指定脚本名称，例如 `update-ddns`。这个名称后面配置定时任务时要用。

以下脚本会直接请求本服务更新阿里云 DNS 记录。默认不传 `ip` 参数，由服务端使用请求来源 IP 作为公网 IP：

```routeros
# Update Aliyun DDNS through the proxy service

# DDNS proxy endpoint
:global ddnsUrl "https://ddns.example.com/ddns"

# DDNS proxy token, same as DDNS_PROXY_TOKEN on the server
:global ddnsToken "your-random-token"

# Domain to update
:global ddnsDomain "proxy.example.com"

# Update DNS record
:local results [/tool fetch url=($ddnsUrl . "?token=" . $ddnsToken . "&domain=" . $ddnsDomain) check-certificate=no as-value output=user]

:if ($results->"status" = "finished") do={
    :local result ($results->"data")
    :log warning $result
}
```

注意：本项目的设计目标是让 RouterOS 只保存 `DDNS_PROXY_TOKEN`，不要把阿里云 `AccessKey ID` 和 `AccessKey Secret` 写入 RouterOS。阿里云密钥只应该配置在运行本服务的服务器 `.env` 中。

如果你已经在其他脚本中拿到了公网 IP，也可以直接调用：

```routeros
/tool fetch url=("https://ddns.example.com/ddns?token=your-random-token&domain=proxy.example.com&ip=" . $currentIp) check-certificate=no keep-result=no
```

如果直接使用服务器 IP 和端口，请确认 URL 里包含 `/ddns?`：

```routeros
:global ddnsUrl "http://203.0.113.10:6180/ddns"
:local results [/tool fetch url=($ddnsUrl . "?token=" . $ddnsToken . "&domain=" . $ddnsDomain) check-certificate=no as-value output=user]
```

### 配置定时任务

进入 `[System]` -> `[Scheduler]` -> `[+]`，添加定时任务执行上面的脚本：

```routeros
# update-ddns 是上面配置的脚本名称
:execute script="update-ddns"
```

## 安全建议

- 不要把阿里云 AccessKey 配置在路由器上。
- `DDNS_PROXY_TOKEN` 使用足够长的随机字符串。
- 公网部署时启用 HTTPS。
- 为阿里云 RAM 用户配置最小权限。
- 不要提交 `.env` 或任何密钥文件。

## 开发计划

### Docker 部署支持

计划新增 Docker 部署方式，方便在 NAS、VPS、Homelab 服务器和容器平台中运行。

- 新增 `Dockerfile`，使用轻量 Python 基础镜像构建运行环境。
- 新增 `.dockerignore`，避免把 `.env`、`.venv`、缓存和 IDE 配置打进镜像。
- 新增 `docker-compose.yml.example`，支持通过 `env_file: .env` 读取配置。
- 在 `Makefile` 中新增 `docker-build`、`docker-run`、`docker-compose-up` 等命令。
- README 增加 Docker 安装、启动、停止、查看日志和升级步骤。
- 明确容器默认暴露 `6180` 端口，并支持通过反向代理提供 HTTPS。
- 增加部署验证命令，确认 `/ddns` 接口能正常返回 `401`、`400` 等预期状态。

预期使用方式：

```bash
cp .env.example .env
vim .env
docker compose up -d
```

或者：

```bash
docker run -d \
  --name ros-aliyun-ddns \
  --restart unless-stopped \
  --env-file .env \
  -p 6180:6180 \
  ros-aliyun-ddns:latest
```

## Contributors

- miaoyc
- Codex

## 常见错误

- `401 unauthorized`：`token` 不正确。
- `400 missing domain`：缺少 `domain` 参数。
- `404`：请求路径不正确。确认 RouterOS 脚本里的服务地址是 `/ddns?token=...&domain=...&ip=...`，不是服务器根路径，也不是 `/token=...`。
- `500`：阿里云接口调用失败、权限不足、域名不在当前账号下，或环境变量未正确配置。
