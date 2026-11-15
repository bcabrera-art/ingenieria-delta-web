/**
 * INGENIERÍA DELTA / DELTA AYSÉN — Runtime interactivo unificado
 * - Video hero con bucle suavizado y scroll reveals respetando reduced-motion
 * - Filtro de proyectos reales en Aysén + revelación progresiva del tagline
 * - Simulador SHOWCASE DELTA (módulos 610 Wp / 0,61 kWp + comparativa mensual con opción $0 pie)
 * - Cotizador guiado de 4 pasos conectado al simulador + envío directo a correos y WhatsApp
 */
document.documentElement.classList.add('js');

const DELTA_CONFIG = {
  whatsapp: '56967413329',
  emails: ['bcabrera@ingenieriadelta.cl', 'cdiaz@ingenieriadelta.cl'],
  leadEndpoint: 'enviar.php',
  assistantEnabled: false
};

const LINEAS_LABEL = {
  red: 'Sistema con red eléctrica (bajar cuenta de luz)',
  aislado: 'Sistema 100% autónomo sin red (con baterías)',
  diesel: 'Híbrido / Reemplazo de generador diésel'
};

window.DeltaLeads = (function () {
  function generateRef() {
    const chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
    let code = '';
    for (let i = 0; i < 5; i += 1) {
      code += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return '#DLT-' + code;
  }

  function toMessage(lead) {
    if (lead && !lead.lead_ref) {
      lead.lead_ref = generateRef();
    }
    const lines = [
      'Hola Benjamín y Carlos (Ingeniería Delta), les escribo por un proyecto solar:',
      '',
      '- Ref. Expediente: ' + (lead.lead_ref || '#DLT-WEB'),
      '- Nombre: ' + (lead.nombre || 'Por confirmar'),
      '- Correo: ' + (lead.correo || 'Por confirmar'),
      '- Teléfono / WhatsApp: ' + (lead.telefono || 'Por confirmar'),
      '- Localidad: ' + (lead.ubicacion || 'Región de Aysén'),
      '- Situación: ' + (LINEAS_LABEL[lead.linea] || lead.empresa || 'Sistema solar')
    ];
    if (lead.consumo) {
      lines.push((lead.linea === 'aislado' ? '- Consumos a alimentar: ' : '- Gasto mensual actual: ') + lead.consumo);
    }
    if (lead.linea === 'red' && lead.boletaPdfName) {
      lines.push('- Cuenta eléctrica en PDF adjunta: ' + lead.boletaPdfName);
    }
    if (lead.linea === 'diesel') {
      if (lead.potencia_generador) lines.push('- Potencia del generador instalado: ' + lead.potencia_generador);
      if (lead.fase_generador) lines.push('- Fase del generador: ' + lead.fase_generador);
      if (lead.fotoGenName) lines.push('- Foto del generador adjunta: ' + lead.fotoGenName);
    }
    if (lead.tipo) lines.push('- Lugar de instalación: ' + lead.tipo);
    if (lead.simulacion && lead.simulacion !== 'Evaluación general sin parámetros del simulador') {
      lines.push('');
      lines.push('Simulación en SHOWCASE DELTA (paneles 610 Wp):');
      lines.push(lead.simulacion);
    }
    if (lead.mensaje) {
      lines.push('');
      lines.push('Comentarios adicionales: ' + lead.mensaje);
    }
    return lines.join('\n');
  }

  function whatsappUrl(text) {
    return 'https://wa.me/' + DELTA_CONFIG.whatsapp + '?text=' + encodeURIComponent(text);
  }

  function submit(lead) {
    const text = toMessage(lead);
    return { text, url: whatsappUrl(text) };
  }

  function open(source, linea) {
    const origin = document.getElementById('f-origen');
    if (origin) origin.value = source || 'directo';
    if (DELTA_CONFIG.assistantEnabled && window.DeltaAssistant && typeof window.DeltaAssistant.open === 'function') {
      window.DeltaAssistant.open({ origen: source, linea: linea || null });
      return true;
    }
    return false;
  }

  return { submit, open, toMessage, whatsappUrl, generateRef };
})();

document.addEventListener('DOMContentLoaded', () => {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // =========================================================================
  // 1. NAVEGACIÓN, MENÚ MÓVIL Y VIDEO LOOP SUAVE
  // =========================================================================
  const siteHeader = document.getElementById('site-header');
  if (siteHeader) {
    const syncHeaderScroll = () => {
      siteHeader.classList.toggle('is-scrolled', window.scrollY > 28);
    };
    window.addEventListener('scroll', syncHeaderScroll, { passive: true });
    syncHeaderScroll();
  }

  const menuBtn = document.getElementById('menu-btn');
  const mobilePanel = document.getElementById('mobile-panel');
  const setMenuOpen = (open) => {
    document.body.classList.toggle('menu-open', open);
    if (menuBtn) {
      menuBtn.setAttribute('aria-expanded', String(open));
      menuBtn.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
    }
  };
  if (menuBtn && mobilePanel) {
    menuBtn.addEventListener('click', () => {
      setMenuOpen(!document.body.classList.contains('menu-open'));
    });
    mobilePanel.addEventListener('click', (e) => {
      if (e.target.closest('a')) setMenuOpen(false);
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') setMenuOpen(false);
    });
  }

  const heroVideo = document.getElementById('hero-video');
  if (heroVideo && !prefersReducedMotion) {
    const FADE_SEC = 0.7;
    let isFadingLoop = false;
    heroVideo.addEventListener('timeupdate', () => {
      if (!heroVideo.duration || Number.isNaN(heroVideo.duration)) return;
      const remaining = heroVideo.duration - heroVideo.currentTime;
      if (remaining <= FADE_SEC && !isFadingLoop) {
        isFadingLoop = true;
        heroVideo.classList.add('is-loop-fading');
      } else if (remaining > FADE_SEC + 0.5 && heroVideo.currentTime < 1.2 && isFadingLoop) {
        isFadingLoop = false;
        heroVideo.classList.remove('is-loop-fading');
      }
    });
  } else if (heroVideo && prefersReducedMotion) {
    heroVideo.pause();
  }

  // Enlaces activos en navbar y scroll reveal
  const navLinks = Array.from(document.querySelectorAll('.nav-links a'));
  const revealEls = Array.from(document.querySelectorAll('.reveal'));
  if ('IntersectionObserver' in window && !prefersReducedMotion) {
    const sections = navLinks
      .map((a) => document.querySelector(a.getAttribute('href')))
      .filter(Boolean);
    if (sections.length) {
      const navObs = new IntersectionObserver(
        (entries) => {
          entries.forEach((en) => {
            if (!en.isIntersecting) return;
            navLinks.forEach((a) => {
              if (a.getAttribute('href') === '#' + en.target.id) {
                a.setAttribute('aria-current', 'true');
              } else {
                a.removeAttribute('aria-current');
              }
            });
          });
        },
        { rootMargin: '-42% 0px -52% 0px' }
      );
      sections.forEach((s) => navObs.observe(s));
    }

    const revObs = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((en) => {
          if (en.isIntersecting) {
            en.target.classList.add('in');
            observer.unobserve(en.target);
          }
        });
      },
      { rootMargin: '0px 0px -7% 0px', threshold: 0.05 }
    );
    revealEls.forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight * 0.96) {
        el.classList.add('in');
      } else {
        revObs.observe(el);
      }
    });
  } else {
    revealEls.forEach((el) => el.classList.add('in'));
  }

  // Revelación palabra por palabra del tagline
  const tagEl = document.getElementById('tagline');
  if (tagEl) {
    tagEl.innerHTML = tagEl.innerHTML
      .split('<br>')
      .map((line) =>
        line
          .trim()
          .split(/\s+/)
          .map((w) => '<span class="w">' + w + '</span>')
          .join(' ')
      )
      .join('<br>');
    const words = Array.from(tagEl.querySelectorAll('.w'));
    if (prefersReducedMotion || !('IntersectionObserver' in window)) {
      words.forEach((w) => w.classList.add('on'));
    } else {
      let ticking = false;
      const updateTagline = () => {
        ticking = false;
        const thresholdY = window.innerHeight * 0.68;
        words.forEach((w) => {
          w.classList.toggle('on', w.getBoundingClientRect().top < thresholdY);
        });
      };
      const onTagScroll = () => {
        if (!ticking) {
          ticking = true;
          requestAnimationFrame(updateTagline);
        }
      };
      new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
          window.addEventListener('scroll', onTagScroll, { passive: true });
          updateTagline();
        } else {
          window.removeEventListener('scroll', onTagScroll);
        }
      }).observe(tagEl);
    }
  }

  // =========================================================================
  // 2. MODELO SOLAR PATAGÓNICO (ESTÁNDAR 610 Wp / 0,61 kWp)
  // =========================================================================
  const PANEL_WP = 610;
  const PANEL_KWP = 0.61;
  const MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

  const ZONES = {
    aysen: {
      name: 'Puerto Aysén y Litoral',
      yieldPerKwp: 1180,
      tariffClp: 215,
      climateNote: 'Clima marítimo lluvioso. En verano los días son muy largos y los paneles de 610 Wp captan radiación difusa bajo cielo cubierto.',
      recommendedTilt: 'Inclinación recomendada: 38° a 45° hacia el Norte',
      seasonalWeights: [0.145, 0.125, 0.098, 0.062, 0.036, 0.025, 0.029, 0.048, 0.078, 0.105, 0.122, 0.127]
    },
    coyhaique: {
      name: 'Coyhaique y Valle Interior',
      yieldPerKwp: 1320,
      tariffClp: 215,
      climateNote: 'Clima frío y más despejado. En invierno el reflejo de la nieve aporta captación adicional a los módulos de 610 Wp.',
      recommendedTilt: 'Inclinación recomendada: 40° a 45° hacia el Norte',
      seasonalWeights: [0.148, 0.128, 0.096, 0.060, 0.034, 0.024, 0.028, 0.047, 0.079, 0.106, 0.123, 0.127]
    },
    chilechico: {
      name: 'Chile Chico y Lago Gral. Carrera',
      yieldPerKwp: 1540,
      tariffClp: 215,
      climateNote: 'Microclima soleado con alta radiación anual y excelente desempeño solar durante todo el año.',
      recommendedTilt: 'Inclinación recomendada: 36° a 42° hacia el Norte',
      seasonalWeights: [0.140, 0.122, 0.098, 0.066, 0.040, 0.030, 0.034, 0.052, 0.080, 0.104, 0.116, 0.118]
    },
    loslagos: {
      name: 'Los Lagos y Los Ríos (Osorno, Valdivia, Pto. Montt)',
      yieldPerKwp: 1250,
      tariffClp: 198,
      climateNote: 'Equilibrio anual sólido para hogares, lecherías, cabañas y comercio que buscan bajar su cuenta eléctrica.',
      recommendedTilt: 'Inclinación recomendada: 34° a 38° hacia el Norte',
      seasonalWeights: [0.144, 0.124, 0.099, 0.064, 0.038, 0.027, 0.031, 0.049, 0.078, 0.104, 0.120, 0.122]
    }
  };

  // Parámetros financieros de referencia para opción en cuotas ($0 pie)
  const DELTA_FINANCING_CONFIG = {
    capexPerKwp: 980000,
    UF: 41199,
    tasaAnual: 0.0648,
    tasaMensual: 0.00524596,
    firstPaymentDeferredMonths: 4,
    gracePeriodNote: '4 meses de gracia inicial: la primera cuota parte con el sistema ya generando ahorro.',
    fees: { 10: 0.116, 15: 0.155, 20: 0.193, 25: 0.225 },
    factors: { 10: 1.130994, 15: 1.183189, 20: 1.236830, 25: 1.269626 },
    suggestion10y: 'Opción sugerida: aportar pie de $1.628.503 o elegir plazo de 15 a 25 años para mantener ahorro neto positivo desde el mes 1.',
    referenceCase: {
      capexClp: 8900000,
      costoUF: 216.02583,
      billBefore: 137500,
      billAfter: 27500,
      monthlySolarSavings: 110000,
      reductionPct: 80,
      scenarios: {
        10: {
          feePct: 0.116,
          factor: 1.130994,
          montoFinanciadoUF: 244.32399,
          cuotaClp: 109919,
          cuotaUF: 2.66800,
          newTotalPocket: 137419,
          netMonthlySavings: 81,
          savingsPct: 0.1,
          suggestion: 'Opción sugerida: aportar pie de $1.628.503 o elegir plazo de 15 a 25 años para mantener ahorro neto positivo desde el mes 1.'
        },
        15: {
          feePct: 0.155,
          factor: 1.183189,
          montoFinanciadoUF: 255.59929,
          cuotaClp: 94783,
          cuotaUF: 2.30059,
          newTotalPocket: 122283,
          netMonthlySavings: 15217,
          savingsPct: 11.1
        },
        20: {
          feePct: 0.193,
          factor: 1.236830,
          montoFinanciadoUF: 267.18729,
          cuotaClp: 83874,
          cuotaUF: 2.03612,
          newTotalPocket: 111374,
          netMonthlySavings: 26126,
          savingsPct: 19.0
        },
        25: {
          feePct: 0.225,
          factor: 1.269626,
          montoFinanciadoUF: 274.27194,
          cuotaClp: 78075,
          cuotaUF: 1.89551,
          newTotalPocket: 105575,
          netMonthlySavings: 31925,
          savingsPct: 23.2
        }
      }
    },
    terms: {
      10: {
        years: 10,
        months: 120,
        factor: 0.0112,
        fee: 0.116,
        ufFactor: 1.130994,
        label: '10 años',
        tag: '120 ctas.',
        desc: '10 años: menor plazo y menor costo financiero total.'
      },
      15: {
        years: 15,
        months: 180,
        factor: 0.0093,
        fee: 0.155,
        ufFactor: 1.183189,
        label: '15 años',
        tag: '180 ctas.',
        desc: '15 años: equilibrio entre cuota mensual y plazo intermedio.'
      },
      20: {
        years: 20,
        months: 240,
        factor: 0.0084,
        fee: 0.193,
        ufFactor: 1.236830,
        label: '20 años',
        tag: '240 ctas.',
        desc: '20 años: cuota mensual cómoda con ahorro neto desde el inicio.'
      },
      25: {
        years: 25,
        months: 300,
        factor: 0.0079,
        fee: 0.225,
        ufFactor: 1.269626,
        label: '25 años',
        tag: '300 ctas.',
        desc: '25 años: cuota mensual mínima en modalidad $0 pie.'
      }
    },
    climatizacion: {
      none: {
        id: 'none',
        label: 'Sin climatización',
        shortLabel: 'Solo Solar',
        cost: 0,
        desc: 'Solo Solar: generación fotovoltaica para consumos generales del hogar.'
      },
      split: {
        id: 'split',
        label: 'Split Inverter aire-aire (Neteo Solar)',
        shortLabel: '+ Split Inverter',
        cost: 1100000,
        desc: 'Split Inverter aire-aire: climatización eficiente compensada por la planta solar vía Net Billing.'
      },
      aerotermia: {
        id: 'aerotermia',
        label: 'Bomba de Calor aire-agua (Aerotermia)',
        shortLabel: '+ Bomba de Calor',
        cost: 3600000,
        desc: 'Bomba de Calor aire-agua: calefacción hidrónica de alta eficiencia compensada con excedentes solares anuales.'
      }
    },
    batteryAddon: {
      cost5kwh: 1950000,
      cost10kwh: 3500000
    },
    disclaimer: 'Simulación referencial en base a paneles de 610 Wp, sujeta a visita técnica y evaluación de condiciones del proyecto.'
  };

  function computeFrenchAmortizationUF(totalCapexClp, termYears) {
    const months = termYears * 12;
    const costoUF = totalCapexClp / DELTA_FINANCING_CONFIG.UF;
    const factor = DELTA_FINANCING_CONFIG.factors[termYears] || DELTA_FINANCING_CONFIG.factors[25];
    const montoFinanciadoUF = costoUF * factor;
    const cuotaUF =
      montoFinanciadoUF *
      (DELTA_FINANCING_CONFIG.tasaMensual / (1 - Math.pow(1 + DELTA_FINANCING_CONFIG.tasaMensual, -months)));
    const cuotaClp = Math.round(cuotaUF * DELTA_FINANCING_CONFIG.UF);
    return { costoUF, montoFinanciadoUF, cuotaUF, cuotaClp };
  }

  const PROFILES = {
    residencial: {
      label: 'Casa o Parcela',
      minBill: 45000,
      maxBill: 450000,
      defaultBill: 135000,
      step: 5000,
      coverageTarget: 0.85,
      subsidyInfo: 'Disponible pago directo o modalidad de financiamiento en cuotas (10 a 25 años con opción $0 pie), además de tramitación SEC TE4 bajo Ley Net Billing 21.118.'
    },
    pyme: {
      label: 'Comercio, Cabañas o PYME',
      minBill: 120000,
      maxBill: 1500000,
      defaultBill: 380000,
      step: 10000,
      coverageTarget: 0.90,
      subsidyInfo: 'Acompañamiento técnico para postulación a fondos CORFO, SERCOTEC y programas regionales para PYMEs.'
    },
    industrial: {
      label: 'Campo, Agro o Industria',
      minBill: 400000,
      maxBill: 3500000,
      defaultBill: 1250000,
      step: 25000,
      coverageTarget: 0.92,
      subsidyInfo: 'Cofinanciamiento INDAP (riego y energía intrapredial), proyectos productivos regionales e ingeniería eléctrica a medida.'
    }
  };

  const SYSTEM_TYPES = {
    hibrido: {
      name: 'Híbrido con Baterías (BESS)',
      coverageBonus: 1.0,
      description: 'Bajas tu cuenta de luz todo el año y sumas respaldo automático en baterías de litio frente a cortes eléctricos.'
    },
    ongrid: {
      name: 'Conectado a la Red (On-Grid)',
      coverageBonus: 0.92,
      description: 'Enfocado en rebajar tu boleta mensual: la energía excedente se inyecta a la red y se descuenta bajo Net Billing.'
    },
    offgrid: {
      name: '100% Autónomo (Sin Red)',
      coverageBonus: 1.05,
      description: 'Para campos, parcelas o faenas sin empalme o con generador diésel. Opera con paneles y almacenamiento en litio.'
    }
  };

  const simState = {
    profile: 'residencial',
    zone: 'aysen',
    systemType: 'hibrido',
    monthlyBillClp: 135000,
    selectedMonthIdx: 0,
    financingMode: 'financiado', // 'financiado' ($0 pie) | 'contado'
    financingTerm: 25, // 10, 15, 20, 25
    climaType: 'none', // 'none' | 'split' | 'aerotermia'
    includeBatteryAddon: false,
    isReferencePreset: false,
    lastResults: null
  };

  // Referencias DOM Simulador
  const profileBtns = document.querySelectorAll('[data-sim-profile]');
  const zoneSelect = document.getElementById('sim-zone');
  const systemBtns = document.querySelectorAll('[data-sim-system]');
  const billSlider = document.getElementById('sim-bill-slider');
  const billDisplay = document.getElementById('sim-bill-display');
  const billMinLabel = document.getElementById('sim-bill-min');
  const billMaxLabel = document.getElementById('sim-bill-max');

  const containerDeltaFinancing = document.getElementById('container-delta-financing');
  const btnFinRefPreset = document.getElementById('btn-fin-ref-preset');
  const deltaTermsContainer = document.getElementById('delta-terms-container');
  const deltaPymeFinancingNote = document.getElementById('delta-pyme-financing-note');
  const modeBtns = document.querySelectorAll('[data-sim-mode]');
  const termBtns = document.querySelectorAll('[data-sim-term]');
  const climaBtns = document.querySelectorAll('[data-sim-clima]');
  const batteryAddonToggle = document.getElementById('sim-battery-addon-toggle');
  const outTermDesc = document.getElementById('out-term-desc');
  const outClimaDesc = document.getElementById('out-clima-desc');
  const outBatteryToggleSubtext = document.getElementById('out-battery-toggle-subtext');

  const deltaPocketComparison = document.getElementById('delta-pocket-comparison');
  const finCardTermLabel = document.getElementById('fin-card-term-label');
  const finPocketCurrent = document.getElementById('fin-pocket-current');
  const finPocketNewTotal = document.getElementById('fin-pocket-new-total');
  const finPocketNewBill = document.getElementById('fin-pocket-new-bill');
  const finPocketFee = document.getElementById('fin-pocket-fee');
  const finPocketFeeLabel = document.getElementById('fin-pocket-fee-label');
  const finPocketNetSavings = document.getElementById('fin-pocket-net-savings');
  const finPocketAnnualNet = document.getElementById('fin-pocket-annual-net');
  const finPocketEquipmentSummary = document.getElementById('fin-pocket-equipment-summary');
  const finPocketTotalCapex = document.getElementById('fin-pocket-total-capex');
  const finGracePeriodNote = document.getElementById('fin-grace-period-note');
  const finSuggestionNote = document.getElementById('fin-suggestion-note');
  const finAerotermiaFootnote = document.getElementById('fin-aerotermia-footnote');
  const finTransparencyDisclaimer = document.getElementById('fin-transparency-disclaimer');

  const outKwp = document.getElementById('out-kwp');
  const outPanels = document.getElementById('out-panels');
  const outBess = document.getElementById('out-bess');
  const outBessLabel = document.getElementById('out-bess-label');
  const outAnnualKwh = document.getElementById('out-annual-kwh');
  const outSavingsClp = document.getElementById('out-savings-clp');
  const outMonthlySavingsClp = document.getElementById('out-monthly-savings-clp');
  const outCo2 = document.getElementById('out-co2');
  const outTrees = document.getElementById('out-trees');
  const outZoneNote = document.getElementById('out-zone-note');
  const outTilt = document.getElementById('out-tilt');
  const outSystemDesc = document.getElementById('out-system-desc');
  const outSubsidyText = document.getElementById('out-subsidy-text');
  const chartBarsContainer = document.getElementById('delta-chart-bars');
  const chartMonthDetail = document.getElementById('delta-chart-month-detail');
  const btnLoadSimToQuote = document.getElementById('btn-load-sim-to-quote');

  const fmtClp = (num) => '$' + Math.round(num).toLocaleString('es-CL');
  const fmtNum = (num, decimals = 0) =>
    Number(num).toLocaleString('es-CL', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });

  function calculateSimulation() {
    const profileObj = PROFILES[simState.profile];
    const zoneObj = ZONES[simState.zone];
    const sysObj = SYSTEM_TYPES[simState.systemType];

    const monthlyConsumptionKwh = simState.monthlyBillClp / zoneObj.tariffClp;
    const annualConsumptionKwh = monthlyConsumptionKwh * 12;

    const targetAnnualGenerationKwh = annualConsumptionKwh * profileObj.coverageTarget * sysObj.coverageBonus;
    let rawKwp = targetAnnualGenerationKwh / zoneObj.yieldPerKwp;
    rawKwp = Math.max(PANEL_KWP * 3, rawKwp);

    const numPanels = Math.max(3, Math.ceil(rawKwp / PANEL_KWP));
    const exactKwp = numPanels * PANEL_KWP;
    const annualGenKwh = Math.round(exactKwp * zoneObj.yieldPerKwp);

    let bessKwh = 0;
    if (simState.systemType === 'hibrido') {
      const dailyKwh = monthlyConsumptionKwh / 30;
      bessKwh = Math.max(5, Math.ceil((dailyKwh * 0.45) / 5) * 5);
    } else if (simState.systemType === 'offgrid') {
      const dailyKwh = monthlyConsumptionKwh / 30;
      bessKwh = Math.max(10, Math.ceil((dailyKwh * 1.15) / 5) * 5);
    }

    const effectiveCoverage = Math.min(
      0.96,
      (annualGenKwh / annualConsumptionKwh) * (simState.systemType === 'ongrid' ? 0.88 : 0.94)
    );
    const annualSavingsClp = Math.round(simState.monthlyBillClp * 12 * effectiveCoverage);
    const monthlyAvgSavingsClp = Math.round(annualSavingsClp / 12);

    const co2Tons = (annualGenKwh * 0.38) / 1000;
    const equivalentTrees = Math.max(5, Math.round(co2Tons * 45));
    const monthlyGenArray = zoneObj.seasonalWeights.map((w) => Math.round(annualGenKwh * w));

    const solarCapex = Math.round(exactKwp * DELTA_FINANCING_CONFIG.capexPerKwp);
    const climaObj = DELTA_FINANCING_CONFIG.climatizacion[simState.climaType] || DELTA_FINANCING_CONFIG.climatizacion.none;
    const climaCapex = climaObj.cost;

    let batteryCapex = 0;
    let batteryAddonLabel = 'Sin batería adicional';
    if (simState.includeBatteryAddon) {
      if (bessKwh >= 10) {
        batteryCapex = DELTA_FINANCING_CONFIG.batteryAddon.cost10kwh;
        batteryAddonLabel = 'Batería Litio LiFePO4 10 kWh (+3.50M)';
      } else {
        batteryCapex = DELTA_FINANCING_CONFIG.batteryAddon.cost5kwh;
        batteryAddonLabel = 'Batería Litio LiFePO4 5 kWh (+1.95M)';
      }
    }

    // Exclusivamente la planta solar (+ baterías LiFePO4 si aplica) entra al financiamiento en cuotas.
    const financedCapex = solarCapex + batteryCapex;
    const totalProjectCapex = solarCapex + climaCapex + batteryCapex;

    let currentBill = simState.monthlyBillClp;
    let newElectricBill = Math.max(0, currentBill - monthlyAvgSavingsClp);
    let displayCapex = financedCapex;

    const termConfig = DELTA_FINANCING_CONFIG.terms[simState.financingTerm] || DELTA_FINANCING_CONFIG.terms[25];
    let monthlyInstallment;
    let newTotalPocketExpense;
    let netMonthlySavings;
    let netAnnualSavings;
    let isReferenceCase = false;
    let suggestion10y = '';

    if (simState.isReferencePreset) {
      isReferenceCase = true;
      currentBill = DELTA_FINANCING_CONFIG.referenceCase.billBefore;
      newElectricBill = DELTA_FINANCING_CONFIG.referenceCase.billAfter;
      displayCapex = DELTA_FINANCING_CONFIG.referenceCase.capexClp;
      const refScenario =
        DELTA_FINANCING_CONFIG.referenceCase.scenarios[simState.financingTerm] ||
        DELTA_FINANCING_CONFIG.referenceCase.scenarios[25];
      monthlyInstallment = refScenario.cuotaClp;
      newTotalPocketExpense = refScenario.newTotalPocket;
      netMonthlySavings = refScenario.netMonthlySavings;
      netAnnualSavings = netMonthlySavings * 12;
      if (refScenario.suggestion) {
        suggestion10y = refScenario.suggestion;
      }
    } else {
      monthlyInstallment = Math.round(financedCapex * termConfig.factor);
      newTotalPocketExpense = newElectricBill + monthlyInstallment;
      netMonthlySavings = currentBill - newTotalPocketExpense;
      netAnnualSavings = netMonthlySavings * 12;
      if (simState.financingTerm === 10 && netMonthlySavings < currentBill * 0.1) {
        suggestion10y = DELTA_FINANCING_CONFIG.suggestion10y;
      }
    }

    const paybackYears = monthlyAvgSavingsClp > 0 ? displayCapex / (monthlyAvgSavingsClp * 12) : 0;

    simState.lastResults = {
      profileLabel: profileObj.label,
      zoneName: zoneObj.name,
      systemName: sysObj.name,
      monthlyBillClp: currentBill,
      exactKwp,
      numPanels,
      bessKwh,
      annualGenKwh,
      annualSavingsClp,
      monthlyAvgSavingsClp,
      effectiveCoveragePct: Math.round(effectiveCoverage * 100),
      co2Tons,
      equivalentTrees,
      monthlyGenArray,
      solarCapex,
      climaCapex,
      climaObj,
      batteryCapex,
      batteryAddonLabel,
      financedCapex,
      totalProjectCapex: displayCapex,
      fullSystemCapex: totalProjectCapex,
      currentBill,
      newElectricBill,
      termConfig,
      monthlyInstallment,
      newTotalPocketExpense,
      netMonthlySavings,
      netAnnualSavings,
      paybackYears,
      isReferenceCase,
      suggestion10y,
      gracePeriodNote: DELTA_FINANCING_CONFIG.gracePeriodNote
    };

    renderSimulationUI();
  }

  function renderMonthlyChart(monthlyGenArray) {
    if (!chartBarsContainer) return;
    const maxVal = Math.max(...monthlyGenArray, 1);
    chartBarsContainer.innerHTML = '';

    monthlyGenArray.forEach((val, idx) => {
      const heightPct = Math.max(14, Math.round((val / maxVal) * 100));
      const isSelected = idx === simState.selectedMonthIdx;

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'sim-bar-btn' + (isSelected ? ' is-selected' : '');
      btn.setAttribute('aria-label', `${MONTHS[idx]}: ${val} kWh estimados`);
      btn.innerHTML = `
        <span class="sim-bar-val">${fmtNum(val)}</span>
        <div class="sim-bar-col" style="height: ${heightPct}%"></div>
        <span class="sim-bar-month">${MONTHS[idx]}</span>
      `;
      btn.addEventListener('click', () => {
        simState.selectedMonthIdx = idx;
        renderMonthlyChart(monthlyGenArray);
      });
      btn.addEventListener('mouseenter', () => {
        if (chartMonthDetail) {
          chartMonthDetail.textContent = `${MONTHS[idx]}: ${fmtNum(val)} kWh generados (${fmtClp(
            val * ZONES[simState.zone].tariffClp
          )} equivalentes)`;
        }
      });
      chartBarsContainer.appendChild(btn);
    });

    const selVal = monthlyGenArray[simState.selectedMonthIdx] || 0;
    if (chartMonthDetail) {
      chartMonthDetail.textContent = `${MONTHS[simState.selectedMonthIdx]}: ${fmtNum(selVal)} kWh generados (${fmtClp(
        selVal * ZONES[simState.zone].tariffClp
      )} equivalentes)`;
    }
  }

  function buildSimulationSummaryText(r) {
    if (!r) return 'Evaluación general sin parámetros del simulador';
    const parts = [
      `Perfil: ${r.profileLabel}`,
      `Ubicación referencial: ${r.zoneName}`,
      `Arquitectura: ${r.systemName}`,
      `Boleta actual: ${fmtClp(r.monthlyBillClp)}/mes`,
      `Planta estimada: ${fmtNum(r.exactKwp, 2)} kWp (${r.numPanels} paneles de ${PANEL_WP} Wp)`
    ];
    if (r.bessKwh > 0) parts.push(`Almacenamiento Litio BESS: ${fmtNum(r.bessKwh, 0)} kWh`);
    parts.push(`Generación anual estimada: ${fmtNum(r.annualGenKwh)} kWh/año`);
    parts.push(`Ahorro bruto estimado: ${fmtClp(r.annualSavingsClp)}/año`);
    if (simState.profile === 'residencial') {
      if (simState.financingMode === 'financiado') {
        parts.push(
          `Modalidad seleccionada: Opción $0 pie a ${r.termConfig.years} años (cuota referencial ${fmtClp(
            r.monthlyInstallment
          )}/mes, ahorro neto mes 1: ${r.netMonthlySavings >= 0 ? '+' : ''}${fmtClp(r.netMonthlySavings)}/mes, 4 meses de gracia)`
        );
      } else {
        parts.push(`Modalidad seleccionada: Pago directo / contado (inversión est. ${fmtClp(r.totalProjectCapex)})`);
      }
      if (r.climaObj && r.climaObj.cost > 0) {
        parts.push(`Climatización para neteo solar: ${r.climaObj.label}`);
      }
    }
    return parts.join(' | ');
  }

  function syncActiveControls() {
    profileBtns.forEach((b) => {
      const active = b.getAttribute('data-sim-profile') === simState.profile;
      b.setAttribute('aria-pressed', String(active));
      b.classList.toggle('is-active', active);
    });
    systemBtns.forEach((b) => {
      const active = b.getAttribute('data-sim-system') === simState.systemType;
      b.setAttribute('aria-pressed', String(active));
      b.classList.toggle('is-active', active);
    });
    modeBtns.forEach((b) => {
      const active = b.getAttribute('data-sim-mode') === simState.financingMode;
      b.setAttribute('aria-pressed', String(active));
      b.classList.toggle('is-active', active);
    });
    termBtns.forEach((b) => {
      const active = Number(b.getAttribute('data-sim-term')) === simState.financingTerm;
      b.setAttribute('aria-pressed', String(active));
      b.classList.toggle('is-active', active);
    });
    climaBtns.forEach((b) => {
      const active = b.getAttribute('data-sim-clima') === simState.climaType;
      b.setAttribute('aria-pressed', String(active));
      b.classList.toggle('is-active', active);
    });
    if (btnFinRefPreset) {
      btnFinRefPreset.classList.toggle('is-active', simState.isReferencePreset);
      btnFinRefPreset.setAttribute('aria-pressed', String(simState.isReferencePreset));
    }
    if (batteryAddonToggle) {
      batteryAddonToggle.checked = simState.includeBatteryAddon;
    }
  }

  function renderSimulationUI() {
    const r = simState.lastResults;
    if (!r) return;

    const zoneObj = ZONES[simState.zone];
    const sysObj = SYSTEM_TYPES[simState.systemType];
    const profileObj = PROFILES[simState.profile];

    if (billDisplay) billDisplay.textContent = fmtClp(r.monthlyBillClp);
    if (outKwp) outKwp.textContent = `${fmtNum(r.exactKwp, 2)} kWp`;
    if (outPanels) outPanels.textContent = `${r.numPanels} paneles de ${PANEL_WP} Wp`;

    if (outBess) {
      if (r.bessKwh > 0) {
        outBess.textContent = `${fmtNum(r.bessKwh, 0)} kWh Litio`;
        if (outBessLabel) outBessLabel.textContent = 'Respaldo nocturno y cortes eléctricos';
      } else {
        outBess.textContent = 'Sin baterías (On-Grid)';
        if (outBessLabel) outBessLabel.textContent = 'Inyección directa Net Billing a la red';
      }
    }

    if (outAnnualKwh) outAnnualKwh.textContent = `${fmtNum(r.annualGenKwh)} kWh / año`;
    if (outSavingsClp) outSavingsClp.textContent = fmtClp(r.annualSavingsClp);
    if (outMonthlySavingsClp) {
      outMonthlySavingsClp.textContent = `Ahorro prom. ${fmtClp(r.monthlyAvgSavingsClp)}/mes (~${r.effectiveCoveragePct}% boleta)`;
    }
    if (outCo2) outCo2.textContent = `${fmtNum(r.co2Tons, 1)} ton CO2 evitadas / año`;
    if (outTrees) outTrees.textContent = `Equivalente a plantar ${fmtNum(r.equivalentTrees)} árboles nativos`;
    if (outZoneNote) outZoneNote.textContent = zoneObj.climateNote;
    if (outTilt) outTilt.textContent = zoneObj.recommendedTilt;
    if (outSystemDesc) outSystemDesc.textContent = sysObj.description;
    if (outSubsidyText) outSubsidyText.textContent = profileObj.subsidyInfo;

    if (simState.profile === 'residencial') {
      if (containerDeltaFinancing) containerDeltaFinancing.classList.remove('hidden');
      if (deltaPymeFinancingNote) deltaPymeFinancingNote.classList.add('hidden');
      if (deltaPocketComparison) deltaPocketComparison.classList.remove('hidden');

      if (simState.financingMode === 'financiado') {
        if (deltaTermsContainer) deltaTermsContainer.classList.remove('hidden');
        if (finCardTermLabel) finCardTermLabel.textContent = `Opción $0 pie · ${r.termConfig.years} años`;
        if (finPocketCurrent) finPocketCurrent.textContent = fmtClp(r.currentBill);
        if (finPocketNewTotal) finPocketNewTotal.textContent = fmtClp(r.newTotalPocketExpense);
        if (finPocketNewBill) finPocketNewBill.textContent = fmtClp(r.newElectricBill);
        if (finPocketFee) finPocketFee.textContent = fmtClp(r.monthlyInstallment);
        if (finPocketFeeLabel) finPocketFeeLabel.textContent = `Cuota est. (${r.termConfig.years} años):`;

        const barNewBill = document.getElementById('fin-bar-new-bill');
        const barFee = document.getElementById('fin-bar-fee');
        if (barNewBill && barFee && r.currentBill > 0) {
          const billPct = Math.min(45, Math.max(10, Math.round((r.newElectricBill / r.currentBill) * 100)));
          const feePct = Math.min(80, Math.max(15, Math.round((r.monthlyInstallment / r.currentBill) * 100)));
          barNewBill.style.width = `${billPct}%`;
          barFee.style.width = `${Math.min(100 - billPct, feePct)}%`;
        }

        if (finPocketNetSavings) {
          finPocketNetSavings.textContent = `${r.netMonthlySavings >= 0 ? '+' : ''}${fmtClp(r.netMonthlySavings)}`;
          finPocketNetSavings.classList.toggle('is-positive', r.netMonthlySavings >= 0);
          finPocketNetSavings.classList.toggle('is-warning', r.netMonthlySavings < 0);
        }
        if (finPocketAnnualNet) {
          if (r.netMonthlySavings >= 0) {
            finPocketAnnualNet.textContent = `Diferencia positiva est. de ${fmtClp(r.netAnnualSavings)}/año`;
          } else {
            finPocketAnnualNet.textContent = `Desembolso adicional de ~${fmtClp(
              Math.abs(r.netAnnualSavings)
            )} al año frente a cuenta eléctrica (compensado por ahorro térmico en leña o gas licuado)`;
          }
        }
      } else {
        if (deltaTermsContainer) deltaTermsContainer.classList.add('hidden');
        if (finCardTermLabel) finCardTermLabel.textContent = 'Pago directo / Contado';
        if (finPocketCurrent) finPocketCurrent.textContent = fmtClp(r.currentBill);
        if (finPocketNewTotal) finPocketNewTotal.textContent = fmtClp(r.newElectricBill);
        if (finPocketNewBill) finPocketNewBill.textContent = fmtClp(r.newElectricBill);
        if (finPocketFee) finPocketFee.textContent = '$0 (Sin cuotas)';
        if (finPocketFeeLabel) finPocketFeeLabel.textContent = 'Cuota mensual:';
        if (finPocketNetSavings) {
          finPocketNetSavings.textContent = `+${fmtClp(r.monthlyAvgSavingsClp)}`;
          finPocketNetSavings.classList.add('is-positive');
          finPocketNetSavings.classList.remove('is-warning');
        }
        if (finPocketAnnualNet) {
          finPocketAnnualNet.textContent = `Retorno simple estimado en ~${fmtNum(r.paybackYears, 1)} años`;
        }
      }

      if (finPocketTotalCapex) finPocketTotalCapex.textContent = fmtClp(r.totalProjectCapex);
      if (finPocketEquipmentSummary) {
        if (r.isReferenceCase) {
          finPocketEquipmentSummary.textContent = 'Planta Solar 5,49 kWp (9 módulos de 610 Wp)';
        } else {
          const eqParts = [`Planta Solar ${fmtNum(r.exactKwp, 2)} kWp (${r.numPanels} módulos de ${PANEL_WP} Wp)`];
          if (r.batteryCapex > 0) eqParts.push('Batería LiFePO4');
          finPocketEquipmentSummary.textContent = eqParts.join(' + ');
        }
      }

      if (outTermDesc) outTermDesc.textContent = r.termConfig.desc;
      if (outClimaDesc && r.climaObj) outClimaDesc.textContent = r.climaObj.desc;
      if (outBatteryToggleSubtext) {
        outBatteryToggleSubtext.textContent = simState.includeBatteryAddon
          ? `${r.batteryAddonLabel} incorporada a la planta`
          : 'Opcional: incluir respaldo en baterías LiFePO4';
      }
      if (finGracePeriodNote) {
        finGracePeriodNote.textContent = DELTA_FINANCING_CONFIG.gracePeriodNote;
        finGracePeriodNote.classList.toggle('hidden', simState.financingMode !== 'financiado');
      }
      if (finSuggestionNote) {
        if (simState.financingMode === 'financiado' && r.suggestion10y) {
          finSuggestionNote.textContent = r.suggestion10y;
          finSuggestionNote.classList.remove('hidden');
        } else {
          finSuggestionNote.classList.add('hidden');
        }
      }
      if (finAerotermiaFootnote) {
        finAerotermiaFootnote.classList.toggle(
          'hidden',
          !(simState.climaType === 'aerotermia' || simState.climaType === 'split')
        );
      }
      if (finTransparencyDisclaimer) {
        finTransparencyDisclaimer.textContent = DELTA_FINANCING_CONFIG.disclaimer;
      }
    } else {
      if (containerDeltaFinancing) containerDeltaFinancing.classList.add('hidden');
      if (deltaPymeFinancingNote) deltaPymeFinancingNote.classList.remove('hidden');
      if (deltaPocketComparison) deltaPocketComparison.classList.add('hidden');
    }

    syncActiveControls();
    renderMonthlyChart(r.monthlyGenArray);
  }

  function applyProfileSliderRange(newProfile, customBill) {
    const pConfig = PROFILES[newProfile];
    if (!pConfig) return;
    simState.profile = newProfile;
    if (billSlider) {
      billSlider.min = pConfig.minBill;
      billSlider.max = pConfig.maxBill;
      billSlider.step = pConfig.step;
      const targetBill = customBill || pConfig.defaultBill;
      billSlider.value = targetBill;
      simState.monthlyBillClp = targetBill;
    } else {
      simState.monthlyBillClp = customBill || pConfig.defaultBill;
    }
    if (billMinLabel) billMinLabel.textContent = fmtClp(pConfig.minBill);
    if (billMaxLabel) billMaxLabel.textContent = fmtClp(pConfig.maxBill);
  }

  profileBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const newProfile = btn.getAttribute('data-sim-profile');
      if (!PROFILES[newProfile]) return;
      simState.isReferencePreset = false;
      if (newProfile === 'residencial') simState.financingMode = 'financiado';
      applyProfileSliderRange(newProfile);
      calculateSimulation();
    });
  });

  if (zoneSelect) {
    zoneSelect.addEventListener('change', (e) => {
      simState.zone = e.target.value;
      calculateSimulation();
    });
  }

  systemBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const newSys = btn.getAttribute('data-sim-system');
      if (!SYSTEM_TYPES[newSys]) return;
      simState.systemType = newSys;
      calculateSimulation();
    });
  });

  if (billSlider) {
    billSlider.addEventListener('input', (e) => {
      simState.isReferencePreset = false;
      simState.monthlyBillClp = Number(e.target.value);
      calculateSimulation();
    });
  }

  modeBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const mode = btn.getAttribute('data-sim-mode');
      if (!mode) return;
      simState.financingMode = mode;
      calculateSimulation();
    });
  });

  termBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const term = Number(btn.getAttribute('data-sim-term'));
      if (!DELTA_FINANCING_CONFIG.terms[term]) return;
      simState.financingMode = 'financiado';
      simState.financingTerm = term;
      calculateSimulation();
    });
  });

  climaBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const clima = btn.getAttribute('data-sim-clima');
      if (!DELTA_FINANCING_CONFIG.climatizacion[clima]) return;
      simState.isReferencePreset = false;
      simState.climaType = clima;
      calculateSimulation();
    });
  });

  if (batteryAddonToggle) {
    batteryAddonToggle.addEventListener('change', (e) => {
      simState.isReferencePreset = false;
      simState.includeBatteryAddon = Boolean(e.target.checked);
      calculateSimulation();
    });
  }

  if (btnFinRefPreset) {
    btnFinRefPreset.addEventListener('click', () => {
      simState.isReferencePreset = !simState.isReferencePreset;
      if (simState.isReferencePreset) {
        simState.financingMode = 'financiado';
        applyProfileSliderRange('residencial', 137500);
      } else {
        applyProfileSliderRange('residencial', 135000);
      }
      calculateSimulation();
    });
  }

  // Sincronización desde las 3 entradas de Hero / Soluciones hacia Simulador y Cotizador
  function selectDeltaLine(linea) {
    if (linea === 'red') {
      simState.isReferencePreset = false;
      simState.financingMode = 'financiado';
      simState.systemType = 'ongrid';
      simState.includeBatteryAddon = false;
      applyProfileSliderRange('residencial', 135000);
    } else if (linea === 'aislado') {
      simState.isReferencePreset = false;
      simState.systemType = 'offgrid';
      simState.includeBatteryAddon = true;
      applyProfileSliderRange('residencial', 145000);
    } else if (linea === 'diesel') {
      simState.isReferencePreset = false;
      simState.systemType = 'hibrido';
      simState.includeBatteryAddon = true;
      applyProfileSliderRange('pyme', 380000);
    }
    calculateSimulation();
  }

  // =========================================================================
  // 3. FILTRO DE PROYECTOS REALES
  // =========================================================================
  const filterBtns = Array.from(document.querySelectorAll('[data-filter]'));
  const projectCards = Array.from(document.querySelectorAll('#project-list .project'));
  filterBtns.forEach((b) => {
    b.addEventListener('click', () => {
      const f = b.dataset.filter;
      filterBtns.forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
      projectCards.forEach((c) => {
        const l = c.dataset.linea;
        c.hidden = !(f === 'todos' || l === 'todos' || l === f);
        c.classList.add('in');
      });
    });
  });

  document.querySelectorAll('.line-case').forEach((a) => {
    a.addEventListener('click', () => {
      if (filterBtns[0]) filterBtns[0].click();
    });
  });

  // =========================================================================
  // 4. COTIZADOR GUIADO DE 4 PASOS + ENVÍO DUAL (EMAIL + WHATSAPP)
  // =========================================================================
  const form = document.getElementById('lead-form');
  if (form) {
    const steps = Array.from(form.querySelectorAll('.q-step'));
    const backBtn = document.getElementById('q-back');
    const countEl = document.getElementById('q-count');
    const barEl = document.getElementById('q-bar');
    const resultEl = document.getElementById('result');
    const resultStatusEl = document.getElementById('result-status');
    const resultTextEl = document.getElementById('result-text');
    const waLinkEl = document.getElementById('wa-link');
    const mailtoLinkEl = document.getElementById('mailto-link');
    const submitBtn = document.getElementById('q-submit-btn');
    const submitText = document.getElementById('q-submit-text');
    const simAttachedPill = document.getElementById('sim-attached-pill');
    const simAttachedText = document.getElementById('sim-attached-text');
    const btnClearSimAttached = document.getElementById('btn-clear-sim-attached');
    const btnNewQuote = document.getElementById('btn-new-quote');

    const TOTAL_STEPS = 4;
    const MAX_FILE_BYTES = 10 * 1024 * 1024;
    const qState = {
      step: 1,
      linea: null,
      attachedSimSummary: null,
      boletaPdfFile: null,
      fotoGenFile: null
    };

    const formatBytes = (bytes) => {
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const setupUploadField = (cfg) => {
      const input = document.getElementById(cfg.inputId);
      const box = document.getElementById(cfg.boxId);
      const labelEl = document.getElementById(cfg.labelId);
      const metaEl = document.getElementById(cfg.metaId);
      const clearBtn = document.getElementById(cfg.clearId);
      const errEl = document.getElementById(cfg.errId);
      if (!input || !box) return;

      const resetUI = (showError) => {
        qState[cfg.stateKey] = null;
        input.value = '';
        box.classList.remove('has-file');
        box.classList.toggle('has-error', Boolean(showError));
        if (labelEl) labelEl.textContent = cfg.defaultLabel;
        if (metaEl) metaEl.textContent = cfg.defaultMeta;
        if (clearBtn) clearBtn.hidden = true;
        if (errEl) errEl.hidden = !showError;
      };

      input.addEventListener('change', () => {
        const file = input.files && input.files[0];
        if (!file) {
          resetUI(false);
          return;
        }
        if (!cfg.validate(file)) {
          resetUI(true);
          return;
        }
        qState[cfg.stateKey] = file;
        box.classList.add('has-file');
        box.classList.remove('has-error');
        if (labelEl) labelEl.textContent = file.name;
        if (metaEl) metaEl.textContent = `${cfg.okPrefix} · ${formatBytes(file.size)}`;
        if (clearBtn) clearBtn.hidden = false;
        if (errEl) errEl.hidden = true;
      });

      if (clearBtn) {
        clearBtn.addEventListener('click', () => resetUI(false));
      }
    };

    setupUploadField({
      inputId: 'f-boleta-pdf',
      boxId: 'boleta-upload-box',
      labelId: 'boleta-pdf-label',
      metaId: 'boleta-pdf-meta',
      clearId: 'btn-clear-boleta-pdf',
      errId: 'e-boleta-pdf',
      stateKey: 'boletaPdfFile',
      defaultLabel: 'Seleccionar archivo PDF de cuenta eléctrica',
      defaultMeta: 'Formato permitido: solo .pdf (máx. 10 MB)',
      okPrefix: 'PDF adjunto',
      validate: (file) => {
        const isPdfExt = /\.pdf$/i.test(file.name);
        const isPdfMime = !file.type || file.type === 'application/pdf';
        return isPdfExt && isPdfMime && file.size <= MAX_FILE_BYTES;
      }
    });

    setupUploadField({
      inputId: 'f-foto-gen',
      boxId: 'foto-gen-upload-box',
      labelId: 'foto-gen-label',
      metaId: 'foto-gen-meta',
      clearId: 'btn-clear-foto-gen',
      errId: 'e-foto-gen',
      stateKey: 'fotoGenFile',
      defaultLabel: 'Seleccionar foto del generador',
      defaultMeta: 'JPG, PNG, WEBP o HEIC (máx. 10 MB)',
      okPrefix: 'Imagen adjunta',
      validate: (file) => {
        const isImgExt = /\.(jpe?g|png|webp|heic|heif)$/i.test(file.name);
        const isImgMime = file.type ? file.type.startsWith('image/') : isImgExt;
        return (isImgExt || isImgMime) && isImgMime && file.size <= MAX_FILE_BYTES;
      }
    });

    const showStep = (step, focus) => {
      qState.step = step;
      steps.forEach((s) => {
        const match = Number(s.dataset.step) === step && (!s.dataset.for || s.dataset.for === qState.linea);
        s.classList.toggle('on', match);
        s.disabled = !match;
      });
      if (resultEl) resultEl.hidden = true;
      if (backBtn) backBtn.hidden = step === 1;
      if (countEl) countEl.textContent = `Paso ${step} de ${TOTAL_STEPS}`;
      if (barEl) barEl.style.transform = `scaleX(${step / TOTAL_STEPS})`;
      if (focus) {
        const cur = form.querySelector('.q-step.on');
        const first =
          cur &&
          (cur.querySelector('input:checked') ||
            cur.querySelector('input:not([type=hidden]):not([type=file]), select'));
        if (first) first.focus({ preventScroll: true });
      }
    };

    const setLinea = (value) => {
      qState.linea = value;
      const radio = form.querySelector(`input[name="linea"][value="${value}"]`);
      if (radio) radio.checked = true;
    };

    const syncAttachedSimUI = () => {
      if (!simAttachedPill || !simAttachedText) return;
      if (qState.attachedSimSummary) {
        const r = simState.lastResults;
        simAttachedText.textContent = r
          ? `Sistema estimado: ${fmtNum(r.exactKwp, 2)} kWp (${r.numPanels} módulos de 610 Wp) · ${r.zoneName}`
          : qState.attachedSimSummary;
        simAttachedPill.classList.remove('hidden');
      } else {
        simAttachedPill.classList.add('hidden');
      }
    };

    if (btnClearSimAttached) {
      btnClearSimAttached.addEventListener('click', () => {
        qState.attachedSimSummary = null;
        syncAttachedSimUI();
      });
    }

    let stepAdvanceTimer = null;
    const scheduleAutoAdvance = (radioEl) => {
      if (!radioEl || radioEl.type !== 'radio') return;
      if (radioEl.name === 'linea') qState.linea = radioEl.value;
      // En el Paso 2 no auto-avanzamos para que el usuario pueda subir su PDF o detallar su generador.
      if (radioEl.name !== 'linea' && radioEl.name !== 'tipo') return;
      const fromStep = qState.step;
      const next = fromStep + 1;
      if (next > TOTAL_STEPS) return;
      clearTimeout(stepAdvanceTimer);
      stepAdvanceTimer = setTimeout(() => {
        if (qState.step === fromStep) showStep(next, true);
      }, prefersReducedMotion ? 0 : 200);
    };

    form.addEventListener('change', (e) => {
      scheduleAutoAdvance(e.target);
    });

    form.addEventListener('click', (e) => {
      const t = e.target;
      if (t && t.tagName === 'INPUT' && t.type === 'radio') {
        scheduleAutoAdvance(t);
      }
    });

    form.querySelectorAll('[data-next]').forEach((b) => {
      b.addEventListener('click', () => showStep(Math.min(TOTAL_STEPS, qState.step + 1), true));
    });

    if (backBtn) {
      backBtn.addEventListener('click', () => showStep(Math.max(1, qState.step - 1), true));
    }

    document.querySelectorAll('[data-cta]').forEach((el) => {
      if (el.tagName === 'BUTTON') return;
      el.addEventListener('click', (e) => {
        const linea = el.getAttribute('data-linea');
        const source = el.getAttribute('data-cta');
        if (window.DeltaLeads.open(source, linea)) {
          e.preventDefault();
          return;
        }
        if (linea) {
          selectDeltaLine(linea);
          setLinea(linea);
          showStep(2);
        } else if (qState.step === 1) {
          showStep(1);
        }
      });
    });

    if (btnLoadSimToQuote) {
      btnLoadSimToQuote.addEventListener('click', () => {
        const r = simState.lastResults;
        if (!r) return;
        qState.attachedSimSummary = buildSimulationSummaryText(r);

        let targetLinea = 'red';
        if (simState.systemType === 'offgrid') targetLinea = 'aislado';
        else if (simState.profile !== 'residencial' && simState.systemType === 'hibrido') targetLinea = 'diesel';
        setLinea(targetLinea);

        const tipoMap = {
          residencial: 'Casa',
          pyme: 'Negocio o PYME',
          industrial: 'Industria o faena'
        };
        const targetTipo = tipoMap[simState.profile] || 'Casa';
        const tipoRadio = form.querySelector(`input[name="tipo"][value="${targetTipo}"]`);
        if (tipoRadio) tipoRadio.checked = true;

        syncAttachedSimUI();
        showStep(4, false);

        const quoteSec = document.getElementById('cotizar');
        if (quoteSec) quoteSec.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth' });
        const nameInput = document.getElementById('f-nombre');
        if (nameInput) setTimeout(() => nameInput.focus({ preventScroll: true }), 420);
      });
    }

    // Validación Step 4 (Nombre, Correo, Teléfono)
    const fields = {
      nombre: {
        el: document.getElementById('f-nombre'),
        err: document.getElementById('e-nombre'),
        ok: (v) => v.trim().length > 1
      },
      correo: {
        el: document.getElementById('f-correo'),
        err: document.getElementById('e-correo'),
        ok: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim())
      },
      telefono: {
        el: document.getElementById('f-telefono'),
        err: document.getElementById('e-telefono'),
        ok: (v) => v.replace(/\D/g, '').length >= 8
      }
    };

    const checkField = (key) => {
      const f = fields[key];
      if (!f || !f.el) return true;
      const valid = f.ok(f.el.value);
      f.el.setAttribute('aria-invalid', valid ? 'false' : 'true');
      if (f.err) f.err.hidden = valid;
      return valid;
    };

    Object.keys(fields).forEach((k) => {
      const f = fields[k];
      if (!f || !f.el) return;
      f.el.addEventListener('blur', () => {
        if (f.el.value) checkField(k);
      });
      f.el.addEventListener('input', () => {
        if (f.el.getAttribute('aria-invalid') === 'true') checkField(k);
      });
    });

    if (btnNewQuote) {
      btnNewQuote.addEventListener('click', () => {
        showStep(1, true);
      });
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (qState.step !== TOTAL_STEPS) return;

      const okNombre = checkField('nombre');
      const okCorreo = checkField('correo');
      const okTel = checkField('telefono');
      if (!okNombre) {
        fields.nombre.el.focus();
        return;
      }
      if (!okCorreo) {
        fields.correo.el.focus();
        return;
      }
      if (!okTel) {
        fields.telefono.el.focus();
        return;
      }

      const checkedVal = (name) => {
        const el = form.querySelector(`input[name="${name}"]:checked`);
        return el ? el.value : '';
      };
      const artefactos = Array.from(form.querySelectorAll('input[name="artefactos"]:checked')).map((c) =>
        c.value.toLowerCase()
      );
      const consumo =
        qState.linea === 'red'
          ? checkedVal('consumo_red')
          : qState.linea === 'diesel'
          ? checkedVal('consumo_diesel')
          : artefactos.join(', ');

      const localidad = (document.getElementById('f-localidad')?.value || '').trim();
      const mensajeExtra = (document.getElementById('f-mensaje')?.value || '').trim();
      const honeypot = (document.getElementById('f-hp')?.value || '').trim();
      const tipoLugar = checkedVal('tipo') || (simState.lastResults ? simState.lastResults.profileLabel : 'Particular / Hogar');
      const potenciaGenerador =
        qState.linea === 'diesel' ? (document.getElementById('f-potencia-gen')?.value || '').trim() : '';
      const faseGenerador = qState.linea === 'diesel' ? checkedVal('fase_generador') : '';
      const boletaPdfFile = qState.linea === 'red' ? qState.boletaPdfFile : null;
      const fotoGenFile = qState.linea === 'diesel' ? qState.fotoGenFile : null;

      const simulacionTexto = qState.attachedSimSummary || 'Evaluación general sin parámetros del simulador';
      const leadRef =
        window.DeltaLeads && typeof window.DeltaLeads.generateRef === 'function'
          ? window.DeltaLeads.generateRef()
          : '#DLT-' + Math.random().toString(36).substring(2, 7).toUpperCase();
      const lead = {
        lead_ref: leadRef,
        linea: qState.linea,
        consumo,
        potencia_generador: potenciaGenerador,
        fase_generador: faseGenerador,
        boletaPdfName: boletaPdfFile ? boletaPdfFile.name : '',
        fotoGenName: fotoGenFile ? fotoGenFile.name : '',
        tipo: tipoLugar,
        nombre: fields.nombre.el.value.trim(),
        correo: fields.correo.el.value.trim(),
        telefono: fields.telefono.el.value.trim(),
        empresa: tipoLugar,
        ubicacion: localidad || 'Región de Aysén',
        servicios: [LINEAS_LABEL[qState.linea] || 'Proyecto solar integral'],
        simulacion: simulacionTexto,
        mensaje: [consumo ? `Referencia consumo: ${consumo}` : '', mensajeExtra].filter(Boolean).join(' · '),
        website_hp: honeypot,
        origen: document.getElementById('f-origen')?.value || 'directo'
      };

      if (submitBtn && submitText) {
        submitBtn.disabled = true;
        submitText.textContent = 'Enviando solicitud...';
      }

      let emailSent = false;
      let phpSent = false;
      const subject = `Nueva Cotización Web [${lead.lead_ref}] - ${lead.nombre} (${lead.ubicacion}) | Ingeniería Delta`;

      try {
        const formData = new FormData();
        formData.append('lead_ref', lead.lead_ref);
        formData.append('linea', lead.linea || '');
        formData.append('consumo', lead.consumo || '');
        formData.append('potencia_generador', lead.potencia_generador || '');
        formData.append('fase_generador', lead.fase_generador || '');
        formData.append('tipo', lead.tipo || '');
        formData.append('nombre', lead.nombre);
        formData.append('correo', lead.correo);
        formData.append('telefono', lead.telefono);
        formData.append('empresa', lead.empresa);
        formData.append('ubicacion', lead.ubicacion);
        lead.servicios.forEach((s) => formData.append('servicios[]', s));
        formData.append('simulacion', lead.simulacion);
        formData.append('mensaje', lead.mensaje);
        formData.append('website_hp', lead.website_hp);
        formData.append('origen', lead.origen);
        if (boletaPdfFile) formData.append('boleta_pdf', boletaPdfFile, boletaPdfFile.name);
        if (fotoGenFile) formData.append('foto_generador', fotoGenFile, fotoGenFile.name);

        const phpRes = await fetch('enviar.php', {
          method: 'POST',
          headers: { Accept: 'application/json' },
          body: formData
        });
        if (phpRes.ok && phpRes.status === 200) {
          const phpJson = await phpRes.json();
          if (phpJson && phpJson.ok) {
            emailSent = true;
            phpSent = true;
          }
        }
      } catch (_) {}

      if (!emailSent && !honeypot) {
        try {
          const fsRes = await fetch('https://formsubmit.co/ajax/bcabrera@ingenieriadelta.cl', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({
              _subject: subject,
              _cc: 'cdiaz@ingenieriadelta.cl',
              _template: 'table',
              Nombre: lead.nombre,
              Perfil_y_Lugar: lead.empresa,
              Correo: lead.correo,
              Telefono_WhatsApp: lead.telefono,
              Ubicacion: lead.ubicacion,
              Situacion_Proyecto: lead.servicios.join(', '),
              Consumo_o_Artefactos: lead.consumo || 'No especificado',
              Potencia_Generador: lead.potencia_generador || 'No aplica / No especificada',
              Fase_Generador: lead.fase_generador || 'No aplica / No especificada',
              Boleta_PDF_Adjunta: lead.boletaPdfName || 'No adjunta',
              Foto_Generador_Adjunta: lead.fotoGenName || 'No adjunta',
              Simulacion_Showcase_Delta_610Wp: lead.simulacion,
              Mensaje: lead.mensaje || 'Sin comentarios adicionales'
            })
          });
          if (fsRes.ok) emailSent = true;
        } catch (_) {}
      }

      const out = window.DeltaLeads.submit(lead);
      const mailtoHref = `mailto:bcabrera@ingenieriadelta.cl,cdiaz@ingenieriadelta.cl?subject=${encodeURIComponent(
        subject
      )}&body=${encodeURIComponent(out.text)}`;

      if (resultStatusEl) {
        const hasAttachment = Boolean(boletaPdfFile || fotoGenFile);
        const attachmentName = boletaPdfFile ? boletaPdfFile.name : fotoGenFile ? fotoGenFile.name : '';
        let statusMsg = emailSent
          ? `Solicitud enviada a bcabrera@ingenieriadelta.cl y cdiaz@ingenieriadelta.cl. Si prefieres agilizar la respuesta, envíanos también el resumen por WhatsApp.`
          : `Tu resumen está listo. Puedes enviarlo directamente por WhatsApp o abrirlo en tu cliente de correo hacia bcabrera@ingenieriadelta.cl y cdiaz@ingenieriadelta.cl.`;
        if (hasAttachment && !phpSent) {
          statusMsg += ` Recuerda adjuntar el archivo "${attachmentName}" directamente al enviar por WhatsApp o correo.`;
        }
        resultStatusEl.textContent = statusMsg;
      }
      if (resultTextEl) resultTextEl.textContent = out.text;
      if (waLinkEl) waLinkEl.href = out.url;
      if (mailtoLinkEl) mailtoLinkEl.href = mailtoHref;

      steps.forEach((s) => s.classList.remove('on'));
      if (resultEl) resultEl.hidden = false;
      if (countEl) countEl.textContent = 'Listo';
      if (barEl) barEl.style.transform = 'scaleX(1)';
      if (backBtn) backBtn.hidden = true;

      if (submitBtn && submitText) {
        submitBtn.disabled = false;
        submitText.textContent = 'Enviar solicitud y preparar WhatsApp';
      }
      if (waLinkEl) waLinkEl.focus({ preventScroll: true });
    });

    showStep(1, false);
  }

  // Inicialización del Simulador SHOWCASE DELTA (610 Wp)
  applyProfileSliderRange('residencial', 135000);
  calculateSimulation();
});
