Create a new HTB operation directory.

Parse the user's input for a box name and target IP. Then run the new_box.sh script:

```bash
./scripts/new_box.sh {BOX_NAME} {TARGET_IP}
```

If the user provided arguments like `/newbox Monitored 10.10.11.248`, extract BOX_NAME=Monitored and TARGET_IP=10.10.11.248.

If arguments are missing, ask the user for:
1. Box name (e.g., Monitored)
2. Target IP (e.g., 10.10.11.248)

After the script runs successfully, report:
- The created directory path
- Next step: `cd {BOX_DIR}/oracle && claude`
