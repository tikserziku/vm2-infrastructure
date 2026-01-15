/**
 * Oracle VM Agent API
 *
 * HTTP API для удалённого управления Oracle VMs
 * Работает на VM2, может выполнять команды на обеих VM
 *
 * Endpoints:
 *   POST /agent/exec     - Execute command
 *   POST /agent/deploy   - Deploy code
 *   GET  /agent/diagnose - Run diagnostics
 *   GET  /agent/logs     - Get service logs
 *   POST /agent/fix      - Auto-fix issues
 */

const express = require('express');
const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(express.json({ limit: '10mb' }));

const PORT = process.env.AGENT_PORT || 8080;
const API_KEY = process.env.AGENT_API_KEY || 'oracle-agent-2026';

// VM Configuration
const VMS = {
  vm1: {
    ip: '92.5.72.169',
    sshKey: '/home/ubuntu/.ssh/vm1_key',
    name: 'main',
    services: ['grok-admin-api', 'grok-voice', 'grok-emilia', 'grok-monitor', 'grok-portal', 'grok-android', 'grok-zigminta']
  },
  vm2: {
    ip: 'localhost',
    name: 'hub',
    services: ['nginx', 'transcriber', 'mcp-hub-storage', 'todo-api', 'jarvis', 'gemini-image', 'veo-video', 'emilia-voice']
  }
};

// Auth middleware
function authCheck(req, res, next) {
  const key = req.headers['x-api-key'] || req.query.key;
  if (key !== API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
}

// Execute command on VM
function execOnVM(vmKey, command, timeout = 30000) {
  return new Promise((resolve) => {
    const vm = VMS[vmKey];
    if (!vm) {
      resolve({ success: false, error: `Unknown VM: ${vmKey}` });
      return;
    }

    let fullCommand;
    if (vmKey === 'vm2') {
      // Local execution
      fullCommand = command;
    } else {
      // SSH to VM1
      fullCommand = `ssh -i ${vm.sshKey} -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@${vm.ip} "${command.replace(/"/g, '\\"')}"`;
    }

    try {
      const output = execSync(fullCommand, {
        timeout,
        encoding: 'utf8',
        maxBuffer: 10 * 1024 * 1024
      });
      resolve({ success: true, vm: vm.name, output: output.trim() });
    } catch (err) {
      resolve({
        success: false,
        vm: vm.name,
        error: err.message,
        output: err.stdout?.toString() || '',
        stderr: err.stderr?.toString() || ''
      });
    }
  });
}

// Check resources before deployment
async function checkResources(vmKey) {
  // Simple commands that work over SSH without escaping issues
  const checks = {
    disk: await execOnVM(vmKey, "df / | tail -1 | awk '{print int($5)}'"),
    memory: await execOnVM(vmKey, "free -m | grep Mem | awk '{print int($7/$2*100)}'"),
    load: await execOnVM(vmKey, "cat /proc/loadavg | cut -d' ' -f1")
  };

  const diskUsage = parseInt(checks.disk.output) || 0;
  const memFree = parseInt(checks.memory.output) || 0;
  const load = parseFloat(checks.load.output) || 0;

  return {
    ok: diskUsage < 90 && memFree > 10,
    disk: { usage: diskUsage, ok: diskUsage < 90 },
    memory: { free: memFree, ok: memFree > 10 },
    load: { value: load, ok: load < 4 },
    message: diskUsage >= 90 ? 'Disk full!' : memFree <= 10 ? 'Memory low!' : 'Resources OK'
  };
}

// ==================== ENDPOINTS ====================

// Health check
app.get('/agent/health', (req, res) => {
  res.json({ status: 'ok', version: '1.0.0', vms: Object.keys(VMS) });
});

// Execute command
app.post('/agent/exec', authCheck, async (req, res) => {
  const { vm, command } = req.body;
  if (!vm || !command) {
    return res.status(400).json({ error: 'vm and command required' });
  }
  const result = await execOnVM(vm, command);
  res.json(result);
});

// Get service logs
app.get('/agent/logs/:vm/:service', authCheck, async (req, res) => {
  const { vm, service } = req.params;
  const lines = req.query.lines || 50;

  let command;
  if (vm === 'vm2' && !service.startsWith('grok')) {
    // PM2 logs for VM2
    command = `pm2 logs ${service} --nostream --lines ${lines} 2>&1 || journalctl -u ${service} -n ${lines} --no-pager`;
  } else {
    // Systemd logs
    command = `journalctl -u ${service} -n ${lines} --no-pager`;
  }

  const result = await execOnVM(vm, command);
  res.json(result);
});

// Diagnose VM
app.get('/agent/diagnose/:vm', authCheck, async (req, res) => {
  const { vm } = req.params;
  const result = await execOnVM(vm, '~/auto_diagnose.sh 2>&1');
  const resources = await checkResources(vm);
  res.json({ ...result, resources });
});

// Check resources
app.get('/agent/resources/:vm', authCheck, async (req, res) => {
  const { vm } = req.params;
  const resources = await checkResources(vm);
  res.json(resources);
});

// Deploy code
app.post('/agent/deploy', authCheck, async (req, res) => {
  const { vm, path: filePath, content, service, restart = true } = req.body;

  if (!vm || !filePath || !content) {
    return res.status(400).json({ error: 'vm, path, content required' });
  }

  // 1. Check resources
  const resources = await checkResources(vm);
  if (!resources.ok) {
    return res.json({
      success: false,
      step: 'resources',
      error: resources.message,
      resources
    });
  }

  // 2. Backup existing file
  const backupCmd = `cp "${filePath}" "${filePath}.bak" 2>/dev/null || true`;
  await execOnVM(vm, backupCmd);

  // 3. Write new content
  const escapedContent = content.replace(/'/g, "'\\''");
  const writeCmd = `cat > "${filePath}" << 'EOFCONTENT'\n${content}\nEOFCONTENT`;
  const writeResult = await execOnVM(vm, writeCmd);

  if (!writeResult.success) {
    return res.json({
      success: false,
      step: 'write',
      error: writeResult.error
    });
  }

  // 4. Restart service if specified
  if (service && restart) {
    let restartCmd;
    if (vm === 'vm2' && !service.startsWith('grok')) {
      restartCmd = `pm2 restart ${service} 2>&1 || sudo systemctl restart ${service}`;
    } else {
      restartCmd = `sudo systemctl restart ${service}`;
    }

    const restartResult = await execOnVM(vm, restartCmd);

    // 5. Check if service is running
    await new Promise(r => setTimeout(r, 2000));
    const statusCmd = vm === 'vm2' && !service.startsWith('grok')
      ? `pm2 show ${service} | grep status || systemctl is-active ${service}`
      : `systemctl is-active ${service}`;
    const statusResult = await execOnVM(vm, statusCmd);

    const isRunning = statusResult.output?.includes('online') || statusResult.output?.includes('active');

    return res.json({
      success: isRunning,
      step: isRunning ? 'complete' : 'restart_failed',
      deployed: filePath,
      service,
      status: statusResult.output,
      restartOutput: restartResult.output
    });
  }

  res.json({ success: true, step: 'complete', deployed: filePath });
});

// Auto-fix with retry
app.post('/agent/fix', authCheck, async (req, res) => {
  const { vm, service, maxRetries = 3 } = req.body;

  if (!vm || !service) {
    return res.status(400).json({ error: 'vm and service required' });
  }

  const attempts = [];

  for (let i = 0; i < maxRetries; i++) {
    // Get logs
    const logsCmd = vm === 'vm2' && !service.startsWith('grok')
      ? `pm2 logs ${service} --nostream --lines 30 2>&1`
      : `journalctl -u ${service} -n 30 --no-pager`;
    const logs = await execOnVM(vm, logsCmd);

    // Analyze and fix
    let fixAction = null;
    const logText = logs.output || '';

    if (logText.includes('EADDRINUSE') || logText.includes('Address already in use')) {
      // Port conflict - find and kill
      const portMatch = logText.match(/port\s*(\d+)/i);
      if (portMatch) {
        fixAction = `fuser -k ${portMatch[1]}/tcp 2>/dev/null || true`;
      }
    } else if (logText.includes('Cannot find module') || logText.includes('MODULE_NOT_FOUND')) {
      // Missing module - npm install
      const moduleMatch = logText.match(/Cannot find module '([^']+)'/);
      if (moduleMatch) {
        fixAction = `cd $(dirname $(pm2 show ${service} | grep 'script path' | awk '{print $4}')) && npm install ${moduleMatch[1]}`;
      }
    } else if (logText.includes('ENOENT') || logText.includes('no such file')) {
      // Missing file - try to restore from backup
      fixAction = `ls *.bak 2>/dev/null | head -1 | xargs -I{} cp {} $(basename {} .bak) || true`;
    }

    // Apply fix
    if (fixAction) {
      await execOnVM(vm, fixAction);
    }

    // Restart service
    const restartCmd = vm === 'vm2' && !service.startsWith('grok')
      ? `pm2 restart ${service} 2>&1`
      : `sudo systemctl restart ${service}`;
    await execOnVM(vm, restartCmd);

    await new Promise(r => setTimeout(r, 3000));

    // Check status
    const statusCmd = vm === 'vm2' && !service.startsWith('grok')
      ? `pm2 show ${service} | grep status`
      : `systemctl is-active ${service}`;
    const status = await execOnVM(vm, statusCmd);

    const isRunning = status.output?.includes('online') || status.output?.includes('active');

    attempts.push({
      attempt: i + 1,
      fixAction,
      status: status.output,
      success: isRunning
    });

    if (isRunning) {
      return res.json({
        success: true,
        message: `Fixed after ${i + 1} attempt(s)`,
        attempts
      });
    }
  }

  res.json({
    success: false,
    message: `Failed after ${maxRetries} attempts`,
    attempts
  });
});

// List services
app.get('/agent/services/:vm', authCheck, async (req, res) => {
  const { vm } = req.params;
  const vmConfig = VMS[vm];

  if (!vmConfig) {
    return res.status(400).json({ error: `Unknown VM: ${vm}` });
  }

  const services = [];

  for (const svc of vmConfig.services) {
    let statusCmd;
    if (vm === 'vm2' && !svc.startsWith('grok') && svc !== 'nginx') {
      statusCmd = `pm2 show ${svc} 2>/dev/null | grep status | awk '{print $4}' || echo 'not found'`;
    } else {
      statusCmd = `systemctl is-active ${svc} 2>/dev/null || echo 'not found'`;
    }

    const result = await execOnVM(vm, statusCmd);
    services.push({
      name: svc,
      status: result.output?.trim() || 'unknown'
    });
  }

  res.json({ vm: vmConfig.name, services });
});

// Cross-reboot
app.post('/agent/reboot/:target', authCheck, async (req, res) => {
  const { target } = req.params;

  if (target === 'vm1') {
    // We're on VM2, reboot VM1
    const result = await execOnVM('vm2', '~/reboot_vm1.sh 2>&1');
    res.json({ success: true, message: 'VM1 reboot initiated', output: result.output });
  } else if (target === 'vm2') {
    // Reboot ourselves - send response first
    res.json({ success: true, message: 'VM2 reboot initiated' });
    setTimeout(() => {
      execSync('sudo reboot');
    }, 1000);
  } else {
    res.status(400).json({ error: 'Invalid target. Use vm1 or vm2' });
  }
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Oracle Agent API running on port ${PORT}`);
  console.log(`VMs: ${Object.keys(VMS).join(', ')}`);
});
