# Tennis Club - Automatic Deployment

## CI/CD Configuration

This repository uses GitHub Actions for automatic deployment to OVH server.

### How it works

1. Push code to `OVHTennis` branch
2. GitHub Actions automatically triggers deployment workflow
3. Workflow connects to OVH server via SSH
4. Server runs `/opt/apps/tennis-club/deploy.sh`
5. Application is deployed with zero downtime

### Deploy manually

If you need to deploy manually on the server:

```bash
sudo -u deploy bash /opt/apps/tennis-club/deploy.sh
```

### Rollback

In case of emergency, rollback to previous version:

```bash
sudo -u deploy bash /opt/apps/tennis-club/rollback.sh
```

### Deployment logs

Check deployment logs:

```bash
tail -f /opt/apps/tennis-club/deploy.log
```

---

🤖 Auto-deployed from branch: OVHTennis
