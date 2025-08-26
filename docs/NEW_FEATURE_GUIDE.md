# 🚀 New Feature Development Guide

## Overview

This guide provides **step-by-step instructions** for AI to build new features in the Niya FastAPI Template. Follow this pattern to maintain consistency and scalability.

## 🏗️ Architecture Pattern

Every feature follows this **4-layer pattern**:

```
Controller → Service → Repository → Database
```

## 📋 Step-by-Step Feature Development

### Step 1: Define the Feature Requirements

**What to specify:**

-   Feature name and purpose
-   Required endpoints (GET, POST, PUT, DELETE)
-   Data models needed
-   Business logic requirements
-   Authentication requirements

**Example:**

```
Feature: User Profile Management
- GET /api/v1/profile - Get user profile
- PUT /api/v1/profile - Update user profile
- Data: name, bio, avatar_url
- Auth: Required
- Business: Email validation, avatar URL validation
```

### Step 2: Create Data Models (`models/`)

**File**: `models/feature_model.py`

**Pattern**:

```python
from pydantic import BaseModel, Field, validator
from typing import Optional

class FeatureModel(BaseModel):
    """Feature data model with validation"""
    field1: str = Field(..., description="Field description")
    field2: Optional[str] = Field(None, description="Optional field")

    @validator('field1')
    def validate_field1(cls, v):
        if len(v) < 3:
            raise ValueError('Field must be at least 3 characters')
        return v

class FeatureResponseModel(BaseModel):
    """Response model for feature"""
    id: str
    field1: str
    field2: Optional[str] = None
    created_at: str
```

**Key Points**:

-   Use `Field()` for descriptions and validation
-   Add `@validator` for custom validation
-   Include response models for API documentation
-   Use `Optional` for nullable fields

### Step 3: Create Repository (`repositorys/`)

**File**: `repositorys/feature_repo.py`

**Pattern**:

```python
from typing import Dict, Any, Optional, List
import logging
from config.supabasedb import get_supabase_client
from core.exceptions import handle_supabase_error

logger = logging.getLogger(__name__)

class FeatureRepository:
    """Feature repository with proper error handling"""

    def __init__(self):
        self.supabase = get_supabase_client()

    def create_feature(self, feature_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new feature with proper error handling"""
        try:
            result = self.supabase.table("features").insert(feature_data).execute()
            logger.info(f"Feature created successfully: {feature_data.get('id')}")
            return {"status": "success", "data": result.data}
        except Exception as e:
            logger.error(f"Feature creation failed: {str(e)}")
            raise handle_supabase_error(e)

    def get_feature(self, feature_id: str) -> Optional[Dict[str, Any]]:
        """Get feature by ID"""
        try:
            result = self.supabase.table("features").select("*").eq("id", feature_id).single().execute()
            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Failed to get feature {feature_id}: {str(e)}")
            return None

    def update_feature(self, feature_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update feature"""
        try:
            result = self.supabase.table("features").update(update_data).eq("id", feature_id).execute()
            logger.info(f"Feature updated successfully: {feature_id}")
            return {"status": "success", "data": result.data}
        except Exception as e:
            logger.error(f"Failed to update feature {feature_id}: {str(e)}")
            raise handle_supabase_error(e)

    def delete_feature(self, feature_id: str) -> Dict[str, str]:
        """Delete feature"""
        try:
            self.supabase.table("features").delete().eq("id", feature_id).execute()
            logger.info(f"Feature deleted successfully: {feature_id}")
            return {"status": "success", "message": "Feature deleted successfully"}
        except Exception as e:
            logger.error(f"Failed to delete feature {feature_id}: {str(e)}")
            raise handle_supabase_error(e)

    def list_features(self, user_id: str = None) -> List[Dict[str, Any]]:
        """List features with optional user filter"""
        try:
            query = self.supabase.table("features").select("*")
            if user_id:
                query = query.eq("user_id", user_id)
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Failed to list features: {str(e)}")
            return []
```

**Key Points**:

-   Always use `get_supabase_client()` for database access
-   Include proper error handling with `handle_supabase_error()`
-   Add logging for all operations
-   Return structured responses with status
-   Use type hints for all methods

### Step 4: Create Service (`services/`)

**File**: `services/feature_service.py`

**Pattern**:

```python
from typing import Dict, Any, Optional, List
import logging
from models.feature_model import FeatureModel, FeatureResponseModel
from repositorys.feature_repo import FeatureRepository
from core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class FeatureService:
    """Feature service with business logic"""

    def __init__(self, feature_repository: FeatureRepository) -> None:
        self.feature_repository = feature_repository

    def create_feature(self, feature: FeatureModel, user_id: str) -> Dict[str, Any]:
        """Create feature with validation"""
        try:
            # Business logic validation
            if not self._validate_feature_data(feature):
                raise ValidationError("Invalid feature data")

            # Prepare data for repository
            feature_data = feature.dict()
            feature_data["user_id"] = user_id

            result = self.feature_repository.create_feature(feature_data)
            logger.info(f"Feature service: Feature created for user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Feature service: Feature creation failed for user {user_id}: {str(e)}")
            raise

    def get_feature(self, feature_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get feature with authorization"""
        try:
            feature = self.feature_repository.get_feature(feature_id)
            if feature and feature.get("user_id") == user_id:
                logger.info(f"Feature service: Feature retrieved for user {user_id}")
                return feature
            return None
        except Exception as e:
            logger.error(f"Feature service: Failed to get feature {feature_id}: {str(e)}")
            return None

    def update_feature(self, feature_id: str, feature: FeatureModel, user_id: str) -> Dict[str, Any]:
        """Update feature with authorization"""
        try:
            # Check ownership
            existing_feature = self.feature_repository.get_feature(feature_id)
            if not existing_feature or existing_feature.get("user_id") != user_id:
                raise ValidationError("Feature not found or access denied")

            # Business logic validation
            if not self._validate_feature_data(feature):
                raise ValidationError("Invalid feature data")

            update_data = feature.dict(exclude_unset=True)
            result = self.feature_repository.update_feature(feature_id, update_data)
            logger.info(f"Feature service: Feature updated for user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Feature service: Feature update failed for user {user_id}: {str(e)}")
            raise

    def delete_feature(self, feature_id: str, user_id: str) -> Dict[str, str]:
        """Delete feature with authorization"""
        try:
            # Check ownership
            existing_feature = self.feature_repository.get_feature(feature_id)
            if not existing_feature or existing_feature.get("user_id") != user_id:
                raise ValidationError("Feature not found or access denied")

            result = self.feature_repository.delete_feature(feature_id)
            logger.info(f"Feature service: Feature deleted for user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Feature service: Feature deletion failed for user {user_id}: {str(e)}")
            raise

    def list_user_features(self, user_id: str) -> List[Dict[str, Any]]:
        """List features for specific user"""
        try:
            features = self.feature_repository.list_features(user_id)
            logger.info(f"Feature service: Listed features for user {user_id}")
            return features
        except Exception as e:
            logger.error(f"Feature service: Failed to list features for user {user_id}: {str(e)}")
            return []

    def _validate_feature_data(self, feature: FeatureModel) -> bool:
        """Custom business logic validation"""
        # Add your custom validation logic here
        return True
```

**Key Points**:

-   Include business logic validation
-   Check user authorization for operations
-   Use dependency injection for repository
-   Add comprehensive logging
-   Handle errors gracefully

### Step 5: Create Controller (`controller/`)

**File**: `controller/feature.py`

**Pattern**:

```python
from fastapi import APIRouter, Request, Response, Depends
from typing import Dict, Any, List
import logging
from models.feature_model import FeatureModel, FeatureResponseModel
from repositorys.feature_repo import FeatureRepository
from services.feature_service import FeatureService
from middleware.auth import require_authentication
from core.exceptions import ValidationError

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services with dependency injection
feature_repository = FeatureRepository()
feature_service = FeatureService(feature_repository)

@router.post("/features")
async def create_feature(
    feature: FeatureModel,
    request: Request
):
    """Create new feature"""
    try:
        user = await require_authentication(request)
        result = feature_service.create_feature(feature, user.user.id)
        return result
    except ValidationError as e:
        return {"status": "fail", "data": str(e.detail)}
    except Exception as e:
        logger.error(f"Create feature error: {str(e)}")
        return {"status": "fail", "data": "Feature creation failed"}

@router.get("/features/{feature_id}")
async def get_feature(
    feature_id: str,
    request: Request
):
    """Get feature by ID"""
    try:
        user = await require_authentication(request)
        feature = feature_service.get_feature(feature_id, user.user.id)

        if feature:
            return {"status": "ok", "data": feature}
        else:
            return {"status": "fail", "data": "Feature not found"}
    except Exception as e:
        logger.error(f"Get feature error: {str(e)}")
        return {"status": "fail", "data": "Failed to get feature"}

@router.put("/features/{feature_id}")
async def update_feature(
    feature_id: str,
    feature: FeatureModel,
    request: Request
):
    """Update feature"""
    try:
        user = await require_authentication(request)
        result = feature_service.update_feature(feature_id, feature, user.user.id)
        return result
    except ValidationError as e:
        return {"status": "fail", "data": str(e.detail)}
    except Exception as e:
        logger.error(f"Update feature error: {str(e)}")
        return {"status": "fail", "data": "Feature update failed"}

@router.delete("/features/{feature_id}")
async def delete_feature(
    feature_id: str,
    request: Request
):
    """Delete feature"""
    try:
        user = await require_authentication(request)
        result = feature_service.delete_feature(feature_id, user.user.id)
        return result
    except ValidationError as e:
        return {"status": "fail", "data": str(e.detail)}
    except Exception as e:
        logger.error(f"Delete feature error: {str(e)}")
        return {"status": "fail", "data": "Feature deletion failed"}

@router.get("/features")
async def list_features(request: Request):
    """List user's features"""
    try:
        user = await require_authentication(request)
        features = feature_service.list_user_features(user.user.id)
        return {"status": "ok", "data": features}
    except Exception as e:
        logger.error(f"List features error: {str(e)}")
        return {"status": "fail", "data": "Failed to list features"}
```

**Key Points**:

-   Use `require_authentication` for protected endpoints
-   Handle exceptions gracefully
-   Return consistent response format
-   Add proper logging
-   Use dependency injection

### Step 6: Register Router (`main.py`)

**Add to main.py**:

```python
from controller.feature import router as feature_router

# Include routers
app.include_router(router, prefix="/api/v1", tags=["authentication"])
app.include_router(feature_router, prefix="/api/v1", tags=["features"])
```

### Step 7: Database Schema (Supabase)

**Create table in Supabase**:

```sql
-- Example table creation
CREATE TABLE features (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    field1 TEXT NOT NULL,
    field2 TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE features ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Users can view own features" ON features
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own features" ON features
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own features" ON features
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own features" ON features
    FOR DELETE USING (auth.uid() = user_id);
```

## 🔧 Common Patterns

### Authentication Patterns

**Protected Endpoint**:

```python
@router.get("/protected")
async def protected_endpoint(request: Request):
    user = await require_authentication(request)
    # Use user.user.id for user operations
```

**Optional Authentication**:

```python
@router.get("/public")
async def public_endpoint(request: Request):
    user = await get_current_user_optional(request)
    # Handle both authenticated and anonymous users
```

### Error Handling Patterns

**Service Layer**:

```python
try:
    result = self.repository.operation(data)
    return {"status": "success", "data": result}
except Exception as e:
    raise handle_supabase_error(e)
```

**Controller Layer**:

```python
try:
    result = service.operation(data)
    return result
except ValidationError as e:
    return {"status": "fail", "data": str(e.detail)}
except Exception as e:
    logger.error(f"Operation error: {str(e)}")
    return {"status": "fail", "data": "Operation failed"}
```

### Response Patterns

**Success Response**:

```python
return {"status": "ok", "data": result_data}
```

**Error Response**:

```python
return {"status": "fail", "data": "Error message"}
```

**List Response**:

```python
return {"status": "ok", "data": items_list}
```

## 📋 Feature Checklist

### Before Implementation

-   [ ] Define feature requirements
-   [ ] Plan database schema
-   [ ] Design API endpoints
-   [ ] Plan authentication requirements

### During Implementation

-   [ ] Create Pydantic models with validation
-   [ ] Implement repository with error handling
-   [ ] Add business logic in service layer
-   [ ] Create controller endpoints
-   [ ] Add authentication middleware
-   [ ] Register router in main.py

### After Implementation

-   [ ] Test all endpoints
-   [ ] Verify error handling
-   [ ] Check authentication flow
-   [ ] Validate response formats
-   [ ] Test database operations
-   [ ] Update documentation

## 🚀 Quick Feature Template

**For AI: Use this template to build any feature**

```python
# 1. Model (models/feature_model.py)
class FeatureModel(BaseModel):
    field1: str = Field(..., description="Description")

# 2. Repository (repositorys/feature_repo.py)
class FeatureRepository:
    def create_feature(self, data): pass
    def get_feature(self, id): pass

# 3. Service (services/feature_service.py)
class FeatureService:
    def create_feature(self, feature, user_id): pass

# 4. Controller (controller/feature.py)
@router.post("/features")
async def create_feature(feature: FeatureModel, request: Request): pass
```

## 🎯 Example: Complete Feature

**Feature**: User Profile Management

**Files Created**:

1. `models/user_profile_model.py` - Profile data models
2. `repositorys/user_profile_repo.py` - Profile database operations
3. `services/user_profile_service.py` - Profile business logic
4. `controller/user_profile.py` - Profile API endpoints

**Endpoints**:

-   `GET /api/v1/profile` - Get user profile
-   `PUT /api/v1/profile` - Update user profile

**Database**: `user_profiles` table with RLS policies

This pattern ensures **consistency**, **scalability**, and **maintainability** across all features.
