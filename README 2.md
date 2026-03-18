
# Abstract

The installation explores the boundary between perception and suggestion through the imagery of the paranormal, rendering perceptible variations of space that normally remain invisible. Inside an abandoned building, three satellite dishes operate as listening devices, intercepting and interpreting environmental fluctuations in real time.

When the presence manifests, the three CRT monitors begin to communicate through a paranormal language: pulsating luminous sequences, appearances and suspensions of the image that articulate an indecipherable system of signs. Simultaneously, the space is traversed by intermittent electronic acoustic impulses, traces of a possible communication.

The work neither affirms nor denies the existence of invisible presences. Rather, it constructs a device that amplifies the environment, transforming minimal physical variations into perceptual events and leaving the visitor to bridge the distance between interference and meaning.


# The structure of the system

### **1. Hardware Architecture & Network**

The system is designed as a distributed Edge/IoT architecture operating over a local Wi-Fi/LAN network using the UDP protocol to ensure minimal latency and real-time responsiveness.

- **Sensor Node (Arduino / ESP32)**
    - Acts as the data acquisition unit
    - Continuously reads:
        - Ultrasonic sensor (distance)
        - Sound sensor (ambient noise via analog pin A0)
    - Sends formatted UDP messages at ~10Hz:
        
        `ACT | Dist: ... | Noise: ...`
        
- **Master Node (Raspberry Pi 1)**
    - Central processing unit (“the brain”)
    - Responsibilities:
        - Receives sensor data via UDP
        - Manages the system state machine (Standby, Booting, Active)
        - Queries external APIs
        - Generates procedural audio
        - Renders visuals for two CRT monitors
        - Coordinates the entire system behavior
- **Slave Node (Raspberry Pi 2)**
    - Visual rendering unit (“satellite”)
    - Receives JSON packets from the master node
    - Executes synchronized rendering on the third monitor based on:
        - Visual instructions
        - Noise levels
        - System state

### **2. Intelligence Engine (Dynamic Prompt System)**

Artificial intelligence is used not as a conversational interface, but as a procedural meaning generator.

- The master node queries **Google Gemini API**
- The prompt is dynamically constructed using real-time environmental data:
    - Energy level
    - Agitation (vibration/noise)
    - Number of satellites above the installation
    - Presence of the ISS
- Strict constraints are imposed:
    - Output must be **a single raw word**
    - The word must relate to **industrial/cement factory context**
    - No full sentences or “ghost clichés” allowed
- **Silence condition:**
    - If system energy falls below a threshold (0.15), no word is generated

### **3. Morse Engine & Custom Audio Synthesis (Sound Design)**

The project evolved from simple sound playback into a fully procedural audio system.

- **Custom Synthesizer (Python / NumPy)**
    - Generates waveforms mathematically in real time
    - Core waveform: triangular wave with **variable bias** (morphing into sawtooth)
- **Extreme Audio Parameters**
    - High amplitude values (≈24.99)
    - Hard clipping distortion
    - Asymmetrical offset
    - Very low frequencies:
        - ~24Hz for Morse signals
        - ~11Hz for interference
- **Resulting Sound**
    - Dense, distorted, industrial
    - Perceived as physical vibration rather than pure tone
    - Similar to a malfunctioning electrical transformer
- **Real-Time Audio Editor**
    - Debug interface on Raspberry Pi 1
    - Live control of:
        - Frequency
        - Amplitude
        - Offset
        - Bias
        - Phase
    - Immediate auditory feedback without restarting the system

### **4. Interference System (Cyber-Physical Interaction)**

Interaction is continuous and analog, not binary. Sensor data directly corrupts and alters system behavior.

- **Proximity (Ultrasonic Sensor)**
    - At < 2 meters, interference increases
    - Effects on Morse output:
        - Audio dropouts (missing dots/dashes)
        - Visual dropouts (black/glitched screens)
        - Temporal jitter (irregular rhythm)
- **Noise / Vibration**
    - Introduces random visual glitches
    - Activates background static noise layer
- **Satellite Data (N2YO API)**
    - Number of satellites acts as a BPM multiplier
    - More satellites → faster, more frenetic Morse transmission

### **5. State Machine & Activation**

The system behavior is governed by a strict state logic:

- **STANDBY**
    - Screens off
    - System inactive
- **BOOTING (Activation)**
    - Requires precise user behavior:
        - Close proximity (presence)
        - Low noise (silence)
    - If conditions are met:
        - System activates a calibration interface
        - Visual style references telemetry systems (amber & cyan tones)
        - Displays:
            - Sonar calibration
            - Satellite tracking
            - Acoustic array
- **ACTIVE**
    - Morse communication begins (audio + visual)
    - Words generated by AI are transmitted sequentially
    - **Message Queue System**
        - Ensures no overlap between words
        - Each word must fully complete
        - Enforces a fixed 2-second pause before the next

### **6. Development Evolution (Process Summary)**

- **Initial Phase**
    - Network setup
    - Multi-screen CRT interface with scanline effects
- **AI Integration**
    - Connection between sensor data and text generation
    - Introduction of the “industrial ghost” concept
- **Controlled Chaos**
    - Morse initially too clean → introduced degradation system
    - Spatial interference tied to user proximity
- **Synchronization**
    - Solved overlapping messages via buffering and timing control
- **Final Identity**
    - Replaced random activation with silence-based ritual
    - Developed custom procedural audio system
    - Transformed standard playback into expressive sound synthesis

---

### System Architecture

The system operates as a tightly integrated real-time system where:

- Physical data (sensors)
- Network communication (UDP architecture)
- Artificial intelligence (dynamic text generation)
- Procedural audio synthesis
- Distributed visual rendering

work simultaneously to produce a unified perceptual experience.

The result is not a representation, but a **live system of signals**, where environmental conditions, machine logic, and human presence continuously interact to construct an unstable and immersive audiovisual phenomenon.


