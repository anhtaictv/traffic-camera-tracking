const { app, BrowserWindow } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const fs = require('fs')
const http = require('http')

const BACKEND_URL = 'http://127.0.0.1:8000'
// dev (chạy unpacked từ electron/): __dirname/.. là project root thật.
// packaged (.exe cài từ installer): __dirname nằm trong resources/app.asar, project
// root thật (chứa src/, python env) không nằm trong gói cài đặt -> fallback về đường
// dẫn cố định trên máy dev này. Backend Python vẫn cần cài sẵn trên máy chạy app.
function resolveProjectRoot() {
  const relative = path.join(__dirname, '..')
  if (fs.existsSync(path.join(relative, 'src', 'api.py'))) return relative
  return 'D:\\App\\Add in'
}
const PROJECT_ROOT = resolveProjectRoot()

let backendProcess = null
let mainWindow = null

function startBackend() {
  backendProcess = spawn('python', ['-m', 'uvicorn', 'src.api:app', '--host', '127.0.0.1', '--port', '8000'], {
    cwd: PROJECT_ROOT,
    stdio: 'inherit',
  })
  backendProcess.on('error', (err) => {
    console.error('Không khởi động được backend Python:', err)
  })
}

function stopBackend() {
  if (!backendProcess) return
  if (process.platform === 'win32') {
    // .kill() không đủ để dừng hẳn uvicorn trên Windows -> taskkill cả process tree
    spawn('taskkill', ['/pid', String(backendProcess.pid), '/T', '/F'])
  } else {
    backendProcess.kill()
  }
  backendProcess = null
}

function waitForBackend(retriesLeft = 60) {
  return new Promise((resolve, reject) => {
    const attempt = (remaining) => {
      http
        .get(BACKEND_URL + '/api/cameras', (res) => {
          res.resume()
          resolve()
        })
        .on('error', () => {
          if (remaining <= 0) {
            reject(new Error('Backend không sẵn sàng sau nhiều lần thử'))
            return
          }
          setTimeout(() => attempt(remaining - 1), 1000)
        })
    }
    attempt(retriesLeft)
  })
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: 'App Add-in',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  try {
    await waitForBackend()
  } catch (err) {
    console.error(err)
  }
  mainWindow.loadURL(BACKEND_URL)
}

app.whenReady().then(() => {
  startBackend()
  createWindow()
})

app.on('window-all-closed', () => {
  stopBackend()
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  stopBackend()
})
