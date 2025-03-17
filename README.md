# GooglePhotosTimeFix

A powerful utility for restoring correct timestamps to media files exported from Google Photos.

## Description

GooglePhotosTimeFix is a Python tool designed to solve a common issue with Google Photos exports through Google Takeout: the loss of original capture timestamps in the file system. While Google preserves this metadata in accompanying JSON files, the actual photo/video files have their creation dates reset to the export date.

This utility scans through directories of exported Google Photos media, finds the corresponding JSON metadata files, and updates each photo or video with its original capture timestamp.

## Features

- **Restores original capture timestamps** for photos and videos
- **Smart matching** between media files and their JSON metadata
- **Support for multiple file formats** (JPEG, PNG, MP4, etc.)
- **Multi-threaded processing** for fast performance
- **Dry run mode** to preview changes without modifying files
- **Detailed logging** of all operations
- **Progress reporting** during processing
- **Handles edited photos and duplicates** intelligently
