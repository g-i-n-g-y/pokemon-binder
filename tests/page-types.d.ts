// Newer browser features the page uses that TypeScript's checker doesn't know about yet.
// Only read by tests/type_check.py; not part of the app.

// Chrome's barcode reader (PSA slab labels)
declare class BarcodeDetector {
  constructor(options?: { formats?: string[] });
  static getSupportedFormats(): Promise<string[]>;
  detect(source: CanvasImageSource | ImageBitmapSource): Promise<{ rawValue: string; format: string }[]>;
}

// iPhone's "added to home screen" flag
interface Navigator {
  standalone?: boolean;
}

// Phone camera zoom and focus (PSA slab scanning)
interface MediaTrackCapabilities {
  zoom?: { min: number; max: number; step?: number };
  focusMode?: string[];
}
interface MediaTrackConstraintSet {
  zoom?: number;
  focusMode?: string;
}
