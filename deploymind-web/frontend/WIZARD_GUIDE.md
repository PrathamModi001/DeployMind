# DeployMind Deployment Wizard

## Overview

The Deployment Wizard is a comprehensive, multi-step interface that guides users through the deployment process with AI-powered recommendations and real-time feedback.

## Features

### 🎯 Core Features
- **6-Step Workflow**: Repository → Instance → Strategy → Environment → Review → Deploy
- **AI Recommendations**: Smart suggestions for instance types and deployment strategies
- **Real-time Validation**: Instant feedback on user input
- **Progress Tracking**: Visual progress indicators throughout the process
- **Deployment Monitoring**: Live status updates during deployment

### ✨ Step-by-Step Guide

#### Step 1: Repository Selection
- **Purpose**: Select the GitHub repository to deploy
- **Features**:
  - Repository validation (owner/repo format)
  - Branch selection with quick-select buttons
  - Optional commit SHA for specific version deployment
  - Visual validation indicators (checkmarks for valid input)

#### Step 2: Instance Configuration
- **Purpose**: Choose or configure EC2 instance
- **Features**:
  - **AI-Powered Recommendation**: Groq LLM suggests optimal instance type
  - **Instance Type Cards**: Visual selection of t2/t3 instance types
  - **Cost Display**: Monthly cost estimates for each instance type
  - **Manual Override**: Option to use existing instance ID
  - **Region Selection**: Choose AWS region

#### Step 3: Deployment Strategy
- **Purpose**: Select deployment method
- **Features**:
  - **AI Recommendation**: Smart strategy suggestion based on deployment history
  - **3 Strategy Options**:
    - **Rolling Update**: Gradual replacement, zero downtime
    - **Blue/Green**: Full environment switch, instant rollback
    - **Canary**: Progressive traffic shifting, lowest risk
  - **Risk Indicators**: Color-coded risk levels
  - **Feature Comparison**: Key benefits of each strategy

#### Step 4: Environment Variables
- **Purpose**: Configure application environment
- **Features**:
  - **Quick Add**: Pre-defined common variables (NODE_ENV, DATABASE_URL, etc.)
  - **Secret Management**: Mark sensitive values with encryption
  - **Visibility Toggle**: Show/hide secret values
  - **Bulk Management**: Add/remove multiple variables
  - **Validation**: Empty variable detection

#### Step 5: Review & Security
- **Purpose**: Final review before deployment
- **Features**:
  - **Configuration Summary**: All settings at a glance
  - **Security Options**:
    - Enable/disable security scanning
    - Automatic rollback on failure
    - Health check monitoring
  - **Pre-deployment Checklist**: Validation status
  - **Risk Warnings**: Alerts for disabled safety features

#### Step 6: Deployment Progress
- **Purpose**: Monitor deployment in real-time
- **Features**:
  - **Live Status Updates**: 4-phase deployment tracking
  - **Visual Indicators**: Icons and colors for each phase
  - **Progress Bar**: Overall completion percentage
  - **Success/Failure States**: Clear outcome messaging
  - **Quick Actions**: View details or return to dashboard

## Architecture

### Component Structure

```
components/wizard/
├── wizard-container.tsx       # Main wizard shell with progress steps
├── wizard-step.tsx            # Reusable step wrapper with navigation
└── steps/
    ├── repository-step.tsx    # Repository selection
    ├── instance-step.tsx      # Instance configuration
    ├── strategy-step.tsx      # Deployment strategy
    ├── environment-step.tsx   # Environment variables
    ├── review-step.tsx        # Final review
    └── deploy-step.tsx        # Deployment progress
```

### Data Flow

```typescript
// Wizard state managed at page level
wizardData = {
  repository: { repository, branch, commit_sha },
  instance: { instance_id, instance_type, region },
  strategy: { strategy },
  environment: { environment_variables[] },
  review: { enable_security_scan, auto_rollback, health_check_enabled }
}

// Each step receives and updates its section
<RepositoryStep
  data={wizardData.repository}
  onChange={(data) => updateStepData('repository', data)}
/>
```

### AI Integration

The wizard integrates with 3 AI endpoints:

1. **Instance Recommendation** (`/api/ai/recommend-instance`)
   - Input: repository, language, traffic estimate
   - Output: recommended instance type, cost, reasoning

2. **Strategy Recommendation** (`/api/ai/recommend-strategy`)
   - Input: current status, deployment count, success rate
   - Output: recommended strategy, risk level, reasoning

3. **Cost Analysis** (future enhancement)
   - Will show cost projections for environment variables

## Testing

### Manual Testing Steps

1. **Repository Step**
   ```
   ✓ Enter invalid repo format → See validation error
   ✓ Enter valid owner/repo → See checkmark
   ✓ Select branch from quick-select → Branch populated
   ✓ Enter commit SHA → Optional field accepts input
   ✓ Click Continue → Move to next step
   ```

2. **Instance Step**
   ```
   ✓ Wait for AI recommendation → See recommended instance
   ✓ Click instance type card → See selection highlight
   ✓ Enter manual instance ID → Clear AI recommendation
   ✓ Change region → Region updated
   ✓ Click Continue → Move to strategy
   ```

3. **Strategy Step**
   ```
   ✓ See AI recommendation → Rolling/Blue-Green/Canary suggested
   ✓ Click strategy card → See features and risk level
   ✓ Review risk indicators → Color-coded badges
   ✓ Click Continue → Move to environment
   ```

4. **Environment Step**
   ```
   ✓ Click "Add Variable" → New empty variable row
   ✓ Click quick-add badge → Pre-filled variable
   ✓ Mark variable as secret → Toggle visibility
   ✓ Show/hide secret → Eye icon works
   ✓ Remove variable → Row deleted
   ✓ Click Continue → Move to review
   ```

5. **Review Step**
   ```
   ✓ See all configuration → Repository, instance, strategy, env vars
   ✓ Toggle security scan → Switch works
   ✓ Toggle auto-rollback → Switch works
   ✓ See warning if auto-rollback off → Yellow alert shown
   ✓ Click "Deploy Now" → Trigger deployment
   ```

6. **Deploy Step**
   ```
   ✓ See deployment progress → 4 phases tracked
   ✓ Watch status updates → Phases change from pending → in_progress → completed
   ✓ See success state → Green checkmarks, success message
   ✓ See failure state (if error) → Red X, error details
   ✓ Click "View Details" → Navigate to deployment page
   ```

### Edge Cases

- **Empty Repository**: Should prevent next step
- **No Instance Selected**: Should prevent next step
- **No Strategy**: Should prevent next step (but has default)
- **Empty Environment Variables**: Should allow (optional)
- **All Toggles Off**: Should show warning but allow deployment
- **API Failures**: Should gracefully fall back to manual selection

## Best Practices

### For Users
1. **Start with AI Recommendations**: Let AI suggest optimal settings
2. **Review Environment Variables**: Double-check sensitive values
3. **Enable Security Features**: Keep auto-rollback and scanning on
4. **Monitor Deployment**: Watch the progress to catch issues early

### For Developers
1. **Keep Steps Focused**: Each step should have one clear purpose
2. **Provide Clear Feedback**: Validate input immediately
3. **Handle Loading States**: Show spinners during AI calls
4. **Graceful Degradation**: Work without AI recommendations
5. **Mobile Responsive**: Wizard should work on all screen sizes

## Accessibility

- **Keyboard Navigation**: All steps navigable via Tab/Enter
- **Screen Readers**: ARIA labels on all interactive elements
- **Color Contrast**: WCAG AA compliant color schemes
- **Focus Indicators**: Clear focus rings on all inputs

## Performance

- **Lazy Loading**: Steps only render when active
- **Debounced Validation**: Input validation debounced 300ms
- **Optimistic Updates**: UI updates immediately, sync later
- **Polling Optimization**: Status polling every 2s during deployment

## Future Enhancements

1. **Save Draft**: Save wizard state and resume later
2. **Templates**: Pre-configured wizard templates for common stacks
3. **Bulk Deploy**: Deploy multiple repos at once
4. **Rollback Wizard**: Step-by-step rollback process
5. **Cost Calculator**: Real-time cost estimation
6. **Validation API**: Backend validation before submission
7. **WebSocket Updates**: Replace polling with real-time updates
8. **Deployment History**: Show previous deployment configs
