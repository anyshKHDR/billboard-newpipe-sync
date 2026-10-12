cat > ~/billboard-newpipe-sync/systemd/README.md <<'EOF'
# systemd deployment

Files for running Chartpipe as a weekly systemd **user** service. No `sudo`
needed — the service runs as your user and logs to your user journal.

## Files

- `chartpipe-sync.service` — the systemd service unit
- `chartpipe-sync.timer` — fires the service every Wednesday at 06:00
- `weekly-sync.sh` — wrapper script that pulls the latest image and runs sync

## Install

```bash
# 1. Copy the unit files
mkdir -p ~/.config/systemd/user
cp chartpipe-sync.service chartpipe-sync.timer ~/.config/systemd/user/

# 2. Copy the wrapper script and make it executable
mkdir -p ~/chartpipe-work
cp weekly-sync.sh ~/chartpipe-work/weekly-sync.sh
chmod +x ~/chartpipe-work/weekly-sync.sh

# 3. Reload systemd and enable the timer
systemctl --user daemon-reload
systemctl --user enable --now chartpipe-sync.timer

# 4. Let user services run without an active login (headless servers)
sudo loginctl enable-linger $USER

# 5. Verify
systemctl --user list-timers chartpipe-sync.timer

# 6. Manual trigger (for testing)
systemctl --user start chartpipe-sync.service
journalctl --user -u chartpipe-sync.service -f
