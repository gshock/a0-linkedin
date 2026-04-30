# LinkedIn v0.2.2 Multi-Image Support Checklist

## Goal
Add support for LinkedIn posts with multiple local images while preserving the existing single-image flow and HEIC/HEIF auto-conversion support.

## Scope

### In scope
- accept multiple local images for a single post
- support mixed image formats in one request
- support HEIC/HEIF by converting those files to JPG before upload
- keep `image_path` support for single-image posts
- add `image_paths` for multi-image posts
- validate each image before upload
- upload multiple media assets
- create a single LinkedIn post that references multiple uploaded images

### Out of scope
- video
- documents
- carousels beyond native multi-image post support
- scheduling
- analytics
- organization live validation

## Input model
- [x] add `image_paths` argument to `linkedin_post`
- [x] keep `image_path` for backward compatibility
- [x] reject calls that provide both `image_path` and `image_paths`
- [x] require at least one image path when multi-image mode is used

## Validation work
- [x] add reusable `validate_image_paths(...)` helper
- [x] validate each path exists and is a file
- [x] validate each extension is supported
- [x] validate each file is non-empty
- [x] validate each file is within size limit
- [x] decide and enforce max image count

## Conversion work
- [x] convert any `.heic` / `.heif` images to JPG before upload
- [x] preserve metadata about original vs uploaded file
- [x] support mixed inputs like JPG + HEIC in one request

## Tool updates
### `/a0/usr/plugins/linkedin/tools/linkedin_post.py`
- [x] accept `image_paths`
- [x] detect single vs multi-image mode
- [x] expose multi-image preview metadata
- [x] route multi-image create requests into the client

## Client updates
### `/a0/usr/plugins/linkedin/helpers/linkedin_client.py`
- [x] add helper to upload multiple image assets
- [x] build final multi-image post payload
- [x] preserve single-image behavior unchanged
- [x] include uploaded asset metadata in results

## Docs updates
- [x] update README for v0.2.2
- [x] add multi-image usage examples
- [x] document limits and caveats

## Testing
- [x] preview with 2 images
- [x] create with 2 JPG images
- [ ] create with JPG + HEIC mix
- [x] reject both `image_path` and `image_paths`
- [x] reject empty `image_paths`
- [x] reject unsupported files
- [x] verify existing single-image path still works

## Acceptance criteria
- [x] single-image posting still works
- [x] HEIC single-image posting still works
- [x] multi-image personal posting works
- [x] mixed JPG/HEIC multi-image posting works
- [x] README and plugin metadata reflect v0.2.2 scope
