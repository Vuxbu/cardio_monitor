export function renderBaseChart(canvas, elevationProfile) {
    // 1. Canvas validation
    if (!canvas) {
        throw new Error('Canvas element not provided');
    }
    if (!(canvas instanceof HTMLCanvasElement)) {
        throw new Error('Provided element is not a canvas');
    }

    // Debug output
    console.log('Initializing chart with canvas:', {
        clientWidth: canvas.clientWidth,
        clientHeight: canvas.clientHeight,
        computedStyle: window.getComputedStyle(canvas)
    });

    // 2. Get 2D context with error handling
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        throw new Error('Failed to get 2D rendering context');
    }

    // 3. Set dimensions with pixel ratio handling
    const devicePixelRatio = window.devicePixelRatio || 1;
    const container = canvas.parentElement;
    const containerWidth = container ? container.clientWidth : canvas.clientWidth;
    
    const displayWidth = Math.floor(containerWidth * devicePixelRatio);
    const displayHeight = Math.floor(150 * devicePixelRatio); // Increased height for better visibility

    // Apply dimensions
    canvas.width = displayWidth;
    canvas.height = displayHeight;
    canvas.style.width = '100%';
    canvas.style.height = '150px';

    // 4. Data validation with detailed errors
    if (!elevationProfile?.length) {
        throw new Error('Empty elevation profile data');
    }

    // 5. Calculate bounds with better safeguards
    const elevations = elevationProfile.map(p => {
        const elevation = p.ele !== undefined ? p.ele : p.elevation;
        const ele = parseFloat(elevation);
        if (isNaN(ele)) throw new Error(`Invalid elevation value: ${p.ele}`);
        return ele;
    });
    
    const maxEle = Math.max(...elevations);
    const minEle = Math.min(...elevations);
    const totalKm = parseFloat(elevationProfile[elevationProfile.length-1].km);

    if (isNaN(totalKm)) {
        throw new Error('Invalid total distance in elevation profile');
    }
    if (maxEle === minEle) {
        console.warn('Elevation data contains no variation - using default range');
        minEle = maxEle - 100; // Default 100m range if flat
    }

    // 6. Enhanced drawing function
    function drawChart() {
    // 1. Clear canvas with opaque background
    ctx.fillStyle = '#FFFFFF'; // Pure white background
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 2. Draw the elevation line with improved styling
    ctx.beginPath();
    elevationProfile.forEach((point, i) => {
        const x = (point.km / totalKm) * canvas.width;
        const normalizedEle = (point.elevation - minEle) / (maxEle - minEle);
        const y = canvas.height - (normalizedEle * canvas.height * 0.9); // 90% of height
        
        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            // Smooth curve between points
            const prev = elevationProfile[i-1];
            const prevX = (prev.km / totalKm) * canvas.width;
            const prevY = canvas.height - ((prev.elevation - minEle) / (maxEle - minEle)) * canvas.height * 0.9; // Fixed this line
            ctx.bezierCurveTo(
                prevX, prevY,
                x, y,
                x, y
            );
        }
    });

    // 3. Style the line for maximum visibility
    ctx.strokeStyle = '#1a73e8'; // Google blue
    ctx.lineWidth = 4 * (window.devicePixelRatio || 1);
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();

    // 4. Add subtle gradient fill below the line
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
    gradient.addColorStop(0, 'rgba(26, 115, 232, 0.2)');
    gradient.addColorStop(1, 'rgba(26, 115, 232, 0.05)');
    ctx.fillStyle = gradient;
    ctx.fill();

}
    // Initial draw
    drawChart();
    
    return {
        canvas,
        ctx,
        dimensions: { maxEle, minEle, totalKm },
        redraw: drawChart,
        updateDimensions() {
            // Handle window resize
            const newWidth = Math.floor((container?.clientWidth || canvas.clientWidth) * devicePixelRatio);
            if (newWidth !== canvas.width) {
                canvas.width = newWidth;
                drawChart();
            }
        }
    };
}