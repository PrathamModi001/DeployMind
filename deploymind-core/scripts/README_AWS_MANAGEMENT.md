# AWS Resource Management Scripts

Scripts to pause and resume AWS resources to avoid unnecessary charges when not using DeployMind.

## 📋 Overview

These scripts help you:
- **Pause**: Stop all running EC2 instances and save their state
- **Resume**: Start previously stopped instances from saved state

## 🚀 Quick Start

### Pause All Resources

```bash
# Dry run first (see what would happen)
python scripts/pause_aws_resources.py --dry-run

# Actually pause resources
python scripts/pause_aws_resources.py

# With EBS snapshots (extra safety)
python scripts/pause_aws_resources.py --snapshot
```

### Resume All Resources

```bash
# Dry run first
python scripts/resume_aws_resources.py --dry-run

# Actually resume resources
python scripts/resume_aws_resources.py
```

## 📖 Detailed Usage

### pause_aws_resources.py

Stops all running EC2 instances and saves state for later resumption.

**Options:**
```bash
--region REGION    AWS region (default: us-east-1)
--dry-run          Show what would be done without doing it
--snapshot         Create EBS snapshots before stopping (safety backup)
```

**What it does:**
1. Lists all running EC2 instances in the region
2. Optionally creates EBS volume snapshots (if `--snapshot` is used)
3. Stops all running instances
4. Saves instance information to `.aws_paused_resources.json`

**Example output:**
```
==============================================================
AWS Resource Pauser
==============================================================
Region: us-east-1
Dry Run: False

Found 2 running instances:
1. i-1234567890abcdef0 (t2.micro)
   Public IP: 54.123.45.67, Private IP: 172.31.0.123
   Tags: Name=DeployMind-Test, Environment=dev

2. i-0fedcba9876543210 (t2.micro)
   Public IP: 54.123.45.68, Private IP: 172.31.0.124
   Tags: Name=DeployMind-Prod, Environment=prod

⚠️  This will STOP all listed instances!
⚠️  Any running applications will be interrupted!

Type 'YES' to confirm: YES

Successfully stopped 2 instances
  - i-1234567890abcdef0: running → stopping
  - i-0fedcba9876543210: running → stopping

Saved state to: .aws_paused_resources.json

==============================================================
✅ AWS resources paused successfully!
==============================================================
State saved to: .aws_paused_resources.json
To resume resources, run: python scripts/resume_aws_resources.py
```

### resume_aws_resources.py

Starts previously stopped instances from saved state.

**Options:**
```bash
--region REGION    AWS region (override region from saved state)
--dry-run          Show what would be done without doing it
--keep-state       Keep state file after resume (for debugging)
```

**What it does:**
1. Reads `.aws_paused_resources.json` to get instance information
2. Verifies each instance's current state
3. Starts all stopped instances
4. Waits for instances to reach 'running' state (max 5 minutes)
5. Displays new IP addresses
6. Removes state file (unless `--keep-state` is used)

**Example output:**
```
==============================================================
AWS Resource Resumer
==============================================================
Dry Run: False

Loaded state from .aws_paused_resources.json
Paused at: 2026-02-12T18:30:00
Region: us-east-1
Instances: 2

Instances to resume (2):
1. i-1234567890abcdef0 (t2.micro)
   Previous IPs: Public=54.123.45.67, Private=172.31.0.123
   Tags: Name=DeployMind-Test, Environment=dev

2. i-0fedcba9876543210 (t2.micro)
   Previous IPs: Public=54.123.45.68, Private=172.31.0.124
   Tags: Name=DeployMind-Prod, Environment=prod

Verifying instance states...
✓ i-1234567890abcdef0: stopped (can be started)
✓ i-0fedcba9876543210: stopped (can be started)

Will start 2 instance(s)
Type 'YES' to confirm: YES

Successfully started 2 instances
  - i-1234567890abcdef0: stopped → pending
  - i-0fedcba9876543210: stopped → pending

Waiting for instances to start (timeout: 300s)...
  i-1234567890abcdef0: pending...
  i-0fedcba9876543210: pending...
  i-1234567890abcdef0: running ✓
  i-0fedcba9876543210: running ✓
All instances are running!

Updated instance information:
  i-1234567890abcdef0:
    Public IP: 54.123.45.70  (may be different)
    Private IP: 172.31.0.123
  i-0fedcba9876543210:
    Public IP: 54.123.45.71  (may be different)
    Private IP: 172.31.0.124

Removed state file: .aws_paused_resources.json

==============================================================
✅ AWS resources resumed successfully!
==============================================================
```

## 💡 Best Practices

### When to Pause

Pause resources when:
- You're done testing for the day/week
- Taking a break from development
- Deploying to production is not needed
- You want to avoid unnecessary charges

### When to Resume

Resume resources when:
- You're ready to continue development
- You need to test deployments
- Applications need to be accessible

### Safety Tips

1. **Always use `--dry-run` first** to see what will happen
2. **Use `--snapshot`** before pausing if you want extra safety
3. **Check AWS Console** after operations to verify state
4. **Keep `.aws_paused_resources.json` safe** - you need it to resume
5. **Note**: Public IPs may change after stop/start (elastic IPs remain)

## 🔧 Requirements

- Python 3.11+
- boto3 installed (`pip install boto3`)
- AWS credentials configured (via AWS CLI or environment variables)
- IAM permissions:
  - `ec2:DescribeInstances`
  - `ec2:StopInstances`
  - `ec2:StartInstances`
  - `ec2:DescribeVolumes` (if using --snapshot)
  - `ec2:CreateSnapshot` (if using --snapshot)
  - `ec2:CreateTags` (if using --snapshot)

## 📁 State File

The scripts use `.aws_paused_resources.json` to track paused resources.

**Location**: Project root directory

**Format**:
```json
{
  "paused_at": "2026-02-12T18:30:00",
  "region": "us-east-1",
  "instances": [
    {
      "instance_id": "i-1234567890abcdef0",
      "instance_type": "t2.micro",
      "launch_time": "2026-02-01T10:00:00",
      "private_ip": "172.31.0.123",
      "public_ip": "54.123.45.67",
      "tags": {
        "Name": "DeployMind-Test",
        "Environment": "dev"
      },
      "snapshot_id": "snap-0123456789abcdef" (if created)
    }
  ]
}
```

**Important**:
- Don't commit this file to git (it's in `.gitignore`)
- Keep a backup if you lose it and need to manually start instances
- The file is automatically deleted after successful resume

## ⚠️ Important Notes

### Public IP Addresses

- **Standard EC2 IPs**: Will change after stop/start
- **Elastic IPs**: Will remain the same
- After resume, check the new IPs in the script output

### EBS Snapshots

- Using `--snapshot` creates backups of EBS volumes
- Snapshots are retained after resume (manual cleanup needed)
- Snapshots cost ~$0.05/GB-month
- Find snapshots in AWS Console with tag `DeployMind=pause-snapshot`

### Stopped vs Terminated

- **Stopped**: Can be restarted (data preserved)
- **Terminated**: Cannot be restarted (data lost)
- These scripts only work with stopped instances

### Cost Savings

When instances are stopped:
- ❌ No EC2 compute charges
- ✅ EBS storage charges still apply (~$0.10/GB-month)
- ✅ Snapshots charged separately
- 💡 **Estimated savings**: ~$8/month per t2.micro instance

## 🐛 Troubleshooting

### "AWS credentials not found"

**Solution**: Configure AWS CLI
```bash
aws configure
# Enter your AWS Access Key ID, Secret, and Region
```

### "No paused resources found"

**Solution**: The state file is missing. Either:
- Run `pause_aws_resources.py` first
- Manually start instances from AWS Console

### "Operation cancelled by user"

**Solution**: You didn't type 'YES' (case-sensitive) when prompted

### Instances won't start

**Possible causes**:
- Instances were terminated (not stopped)
- AWS service issues
- Insufficient capacity in the region
- IAM permission issues

**Solution**: Check AWS Console or run with `--dry-run` to see errors

## 📊 Cost Monitoring

After using these scripts:

1. **Check AWS Billing Dashboard**:
   - https://console.aws.amazon.com/billing/

2. **Set up billing alerts** (recommended):
   ```bash
   aws cloudwatch put-metric-alarm \
     --alarm-name "AWS-Cost-Alert" \
     --metric-name EstimatedCharges \
     --threshold 15.0 \
     --comparison-operator GreaterThanThreshold
   ```

3. **Monitor EC2 usage**:
   - EC2 Dashboard → Running Instances
   - Check "State" column (should be "stopped" when paused)

## 🔄 Workflow Example

```bash
# Start your day
python scripts/resume_aws_resources.py

# Work on deployments...
python presentation/cli/main.py deploy --repo user/repo --instance i-xxx

# End your day
python scripts/pause_aws_resources.py

# Check cost savings
aws ce get-cost-and-usage \
  --time-period Start=2026-02-01,End=2026-02-14 \
  --granularity DAILY \
  --metrics "UnblendedCost"
```

## 📝 Logging

Both scripts log to:
- **Console**: Human-readable output
- **Audit trail**: All actions logged

Check logs for:
- What instances were paused/resumed
- When operations occurred
- Any errors or warnings

## 🆘 Support

If you encounter issues:

1. Run with `--dry-run` to diagnose
2. Check AWS Console for actual instance states
3. Review error messages in output
4. Ensure AWS credentials are valid
5. Verify IAM permissions are sufficient

## 📚 Related Documentation

- AWS EC2: https://docs.aws.amazon.com/ec2/
- boto3 EC2: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html
- AWS Free Tier: https://aws.amazon.com/free/
