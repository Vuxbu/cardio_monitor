import { renderBaseChart } from './chart.js';

const CHART_DEBUG = true;

export class ChartManager {
  constructor() {
    this.chart = null;
    this.initialized = false;
    this._readyPromise = null;
    this._pendingUpdates = [];
    this._lastPositions = { current: null, ghost: null };
  }

  async init(profile) {
    if (this._readyPromise) return this._readyPromise;

    this._readyPromise = new Promise(async (resolve) => {
      try {
        // DOM readiness check
        if (document.readyState !== 'complete') {
          await new Promise(resolve => {
            if (document.readyState === 'complete') resolve();
            else window.addEventListener('load', resolve);
          });
        }

        // Canvas setup
        const canvas = document.getElementById('elevation-chart-canvas');
        if (!canvas) throw new Error('Canvas element not found');
        if (!canvas.getContext) throw new Error('Canvas 2D context not supported');

        // Dimensions
        const container = canvas.parentElement;
        const style = window.getComputedStyle(container);
        const width = parseInt(style.width);
        const height = 150;
        if (isNaN(width)) throw new Error('Invalid container width');
        
        const scale = window.devicePixelRatio || 1;
        canvas.width = Math.floor(width * scale);
        canvas.height = Math.floor(height * scale);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;

        // Chart creation
        const ctx = canvas.getContext('2d');
        this.chart = new Chart(ctx, {
          type: 'line',
          data: { labels: [], datasets: [] },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            plugins: { legend: { display: false } }
          }
        });

        this._initializeDatasets(profile);
        this.initialized = true;
        resolve(this);

      } catch (err) {
        console.error('Chart init failed:', err);
        this.initialized = false;
        resolve(null);
      }
    });

    return this._readyPromise;
  }

  _initializeDatasets(profile) {
    if (!this.chart || !profile?.length) return;

    this.chart.data = {
      labels: profile.map(p => p.km.toFixed(1)),
      datasets: [
        {
          label: 'Elevation',
          data: profile.map(p => p.elevation),
          borderColor: '#3366cc',
          borderWidth: 2,
          fill: true,
          backgroundColor: 'rgba(51, 102, 204, 0.1)',
          tension: 0.4
        },
        {
          label: 'Your Position',
          data: Array(profile.length).fill(null),
          pointBackgroundColor: '#4285F4',
          pointRadius: 8,
          pointBorderColor: 'white',
          pointBorderWidth: 2,
          showLine: false
        },
        {
          label: 'Ghost Runner',
          data: Array(profile.length).fill(null),
          pointBackgroundColor: '#EA4335',
          pointRadius: 6,
          pointBorderColor: '#fff',
          pointBorderWidth: 1,
          showLine: false
        }
      ]
    };
    this._safeChartUpdate();
  }

  async updateMarkers(currentKm, ghostKm = null) {
    if (!this._isValidChart()) {
      this._pendingUpdates.push({ currentKm, ghostKm });
      return;
    }

    try {
      // Update current position
      this._updateDataset(1, currentKm);
      this._lastPositions.current = currentKm;

      // Update ghost position if provided
      if (ghostKm !== null) {
        this._updateDataset(2, ghostKm);
        this._lastPositions.ghost = ghostKm;
      }

      // Throttle updates for smoother animation
      if (Date.now() - (this._lastUpdate || 0) > 100) {
        this._safeChartUpdate();
        this._lastUpdate = Date.now();
      }

    } catch (err) {
      console.error('Marker update failed:', err);
      await this._attemptRecovery();
    }
  }

  _updateDataset(datasetIndex, km) {
    if (!this._isValidChart()) return;

    // Clear previous marker
    this.chart.data.datasets[datasetIndex].data = Array(this.chart.data.labels.length).fill(null);

    // Find the closest data point
    const closestIndex = this._findClosestPointIndex(km);
    if (closestIndex !== -1) {
      this.chart.data.datasets[datasetIndex].data[closestIndex] = 
        this.chart.data.datasets[0].data[closestIndex];
    }
  }

  _findClosestPointIndex(km) {
    let closestIndex = -1;
    let smallestDiff = Infinity;

    this.chart.data.labels.forEach((label, index) => {
      const diff = Math.abs(parseFloat(label) - km);
      if (diff < smallestDiff) {
        smallestDiff = diff;
        closestIndex = index;
      }
    });

    return smallestDiff < 0.1 ? closestIndex : -1;
  }

  _isValidChart() {
    try {
      return (
        this.initialized &&
        this.chart &&
        !this.chart._destroyed &&
        typeof this.chart.update === 'function' &&
        this.chart.data?.labels?.length > 0 &&
        this.chart.data?.datasets?.length >= 3
      );
    } catch (err) {
      console.error('Validation error:', err);
      return false;
    }
  }

  _safeChartUpdate() {
    if (!this._isValidChart()) return;
    
    try {
      this.chart.update({
        duration: 100, // Smoother animation
        easing: 'easeOutQuad',
        lazy: true
      });
    } catch (err) {
      console.warn('Chart update failed:', err);
    }
  }

  async _attemptRecovery() {
    if (!window.elevationProfile) return;
    
    try {
      this.destroy();
      await new Promise(resolve => setTimeout(resolve, 100));
      await this.init(window.elevationProfile);
      
      // Restore positions after recovery
      if (this._lastPositions.current !== null) {
        this._updateDataset(1, this._lastPositions.current);
      }
      if (this._lastPositions.ghost !== null) {
        this._updateDataset(2, this._lastPositions.ghost);
      }
      
      this._safeChartUpdate();
    } catch (err) {
      console.error('Recovery failed:', err);
    }
  }

  destroy() {
    if (this.chart && typeof this.chart.destroy === 'function') {
      this.chart.destroy();
    }
    this.chart = null;
    this.initialized = false;
    this._pendingUpdates = [];
    this._readyPromise = null;
  }
}