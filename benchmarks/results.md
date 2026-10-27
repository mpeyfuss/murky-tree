# murky-tree benchmarks

- Date: 2026-10-27 01:12 UTC
- Refs: `1.1.0` (049b7e1, murky-tree 1.1.0), `v1.2` (d2d074a, murky-tree 1.2.0), `v2` (cba3f96, murky-tree 2.0.0)
- Python: CPython 3.14.3
- Platform: macOS-26.4.1-arm64-arm-64bit-Mach-O (arm)

Times are the best per-call time over several repeats (lower is better). Speedup is baseline time / ref time; **bold** is ≥ 1.1× faster.

| Benchmark | N | `1.1.0` | `v1.2` | vs `1.1.0` | `v2` | vs `1.1.0` |
|---|--:|--:|--:|--:|--:|--:|
| Standard.of | 100 | 4.17 ms | 1.80 ms | **2.31×** | 959.89 µs | **4.34×** |
| Standard.get_proof(index) | 100 | 57.32 µs | 41.15 µs | **1.39×** | 17.25 µs | **3.32×** |
| Standard.get_proof(value) | 100 | 76.80 µs | 57.07 µs | **1.35×** | 26.67 µs | **2.88×** |
| Standard.verify | 100 | 62.76 µs | 47.06 µs | **1.33×** | 22.58 µs | **2.78×** |
| Standard.verify_leaf | 100 | 60.13 µs | 43.95 µs | **1.37×** | 20.14 µs | **2.99×** |
| Standard.get_multi_proof(32) | 100 | 1.01 ms | 751.52 µs | **1.34×** | 362.83 µs | **2.77×** |
| Standard.verify_multi_proof(32) | 100 | 982.29 µs | 719.96 µs | **1.36×** | 344.96 µs | **2.85×** |
| Standard.validate | 100 | 2.30 ms | 1.74 ms | **1.32×** | 867.46 µs | **2.65×** |
| Standard.to_json | 100 | 236.26 µs | 235.15 µs | 1.00× | 237.43 µs | 1.00× |
| Standard.from_json | 100 | 2.30 ms | 1.87 ms | **1.23×** | 1.28 ms | **1.80×** |
| Simple.of | 100 | 1.17 ms | 431.02 µs | **2.72×** | 165.17 µs | **7.09×** |
| Simple.get_proof(index) | 100 | 43.91 µs | 27.49 µs | **1.60×** | 8.72 µs | **5.03×** |
| Simple.verify | 100 | 48.81 µs | 32.35 µs | **1.51×** | 13.99 µs | **3.49×** |
| Simple.get_multi_proof(32) | 100 | 522.33 µs | 296.76 µs | **1.76×** | 98.42 µs | **5.31×** |
| Simple.verify_multi_proof(32) | 100 | 503.60 µs | 266.42 µs | **1.89×** | 79.70 µs | **6.32×** |
| Simple.validate | 100 | 793.85 µs | 324.53 µs | **2.45×** | 48.49 µs | **16.37×** |
| Standard.of | 1,000 | 44.11 ms | 18.34 ms | **2.40×** | 9.76 ms | **4.52×** |
| Standard.get_proof(index) | 1,000 | 79.47 µs | 54.62 µs | **1.45×** | 21.03 µs | **3.78×** |
| Standard.get_proof(value) | 1,000 | 98.57 µs | 70.12 µs | **1.41×** | 30.35 µs | **3.25×** |
| Standard.verify | 1,000 | 84.82 µs | 61.10 µs | **1.39×** | 28.49 µs | **2.98×** |
| Standard.verify_leaf | 1,000 | 81.29 µs | 58.24 µs | **1.40×** | 25.99 µs | **3.13×** |
| Standard.get_multi_proof(32) | 1,000 | 1.48 ms | 1.06 ms | **1.40×** | 457.44 µs | **3.24×** |
| Standard.verify_multi_proof(32) | 1,000 | 1.47 ms | 1.06 ms | **1.40×** | 476.82 µs | **3.09×** |
| Standard.validate | 1,000 | 22.74 ms | 17.24 ms | **1.32×** | 8.71 ms | **2.61×** |
| Standard.to_json | 1,000 | 2.41 ms | 2.32 ms | 1.04× | 2.32 ms | 1.04× |
| Standard.from_json | 1,000 | 23.33 ms | 18.98 ms | **1.23×** | 12.93 ms | **1.81×** |
| Simple.of | 1,000 | 11.85 ms | 4.40 ms | **2.69×** | 1.71 ms | **6.93×** |
| Simple.get_proof(index) | 1,000 | 61.24 µs | 39.72 µs | **1.54×** | 12.44 µs | **4.92×** |
| Simple.verify | 1,000 | 67.25 µs | 46.16 µs | **1.46×** | 19.44 µs | **3.46×** |
| Simple.get_multi_proof(32) | 1,000 | 969.55 µs | 607.34 µs | **1.60×** | 185.83 µs | **5.22×** |
| Simple.verify_multi_proof(32) | 1,000 | 972.09 µs | 601.73 µs | **1.62×** | 204.36 µs | **4.76×** |
| Simple.validate | 1,000 | 7.74 ms | 3.30 ms | **2.35×** | 495.38 µs | **15.62×** |
| Standard.of | 10,000 | 419.73 ms | 186.11 ms | **2.26×** | 97.73 ms | **4.29×** |
| Standard.get_proof(index) | 10,000 | 99.38 µs | 67.56 µs | **1.47×** | 25.17 µs | **3.95×** |
| Standard.get_proof(value) | 10,000 | 116.05 µs | 83.33 µs | **1.39×** | 34.80 µs | **3.33×** |
| Standard.verify | 10,000 | 103.37 µs | 75.21 µs | **1.37×** | 34.25 µs | **3.02×** |
| Standard.verify_leaf | 10,000 | 101.44 µs | 72.19 µs | **1.41×** | 31.69 µs | **3.20×** |
| Standard.get_multi_proof(32) | 10,000 | 2.15 ms | 1.50 ms | **1.43×** | 586.02 µs | **3.67×** |
| Standard.verify_multi_proof(32) | 10,000 | 2.18 ms | 1.54 ms | **1.41×** | 657.65 µs | **3.32×** |
| Standard.validate | 10,000 | 234.96 ms | 171.66 ms | **1.37×** | 88.49 ms | **2.66×** |
| Standard.to_json | 10,000 | 23.38 ms | 23.08 ms | 1.01× | 23.21 ms | 1.01× |
| Standard.from_json | 10,000 | 224.53 ms | 185.17 ms | **1.21×** | 128.65 ms | **1.75×** |
| Simple.of | 10,000 | 118.37 ms | 44.21 ms | **2.68×** | 17.54 ms | **6.75×** |
| Simple.get_proof(index) | 10,000 | 81.36 µs | 52.30 µs | **1.56×** | 16.30 µs | **4.99×** |
| Simple.verify | 10,000 | 89.03 µs | 60.66 µs | **1.47×** | 25.07 µs | **3.55×** |
| Simple.get_multi_proof(32) | 10,000 | 1.71 ms | 1.09 ms | **1.57×** | 328.20 µs | **5.20×** |
| Simple.verify_multi_proof(32) | 10,000 | 1.74 ms | 1.14 ms | **1.53×** | 410.65 µs | **4.24×** |
| Simple.validate | 10,000 | 80.78 ms | 32.93 ms | **2.45×** | 4.98 ms | **16.22×** |
