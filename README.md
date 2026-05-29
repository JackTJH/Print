# TCP 打印上位机

局域网内跨电脑无线传输文件并自动打印。

## 使用方法

| 角色 | 程序 | 说明 |
|------|------|------|
| 服务端（公共电脑） | `PrintServer.exe` | 启动服务，等待接收文件 |
| 客户端（用户电脑） | `PrintClient.exe` | 连接服务端，发送文件 |

1. 服务端电脑连接打印机，设为默认打印机
2. 运行 `PrintServer.exe`，点击 **启动服务**
3. 客户端运行 `PrintClient.exe`，输入服务端 IP，选择文件，点击 **发送**

## 支持格式

PDF、DOCX、XLSX、DOC、XLS、TXT、CSV、PNG、JPG、BMP、TIFF、GIF

## 下载

前往 [Releases](https://github.com/JackTJH/Print/releases) 下载最新版本。

## 运行环境

- Windows 10/11
- 无需安装 Python 或任何依赖，双击即用

## 打印机要求

- Word/Excel 文档需安装 Microsoft Office
- 图片使用系统画图工具静默打印
- PDF 使用 Edge 浏览器打印
