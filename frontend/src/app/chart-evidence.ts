import { AfterViewInit, Component, ElementRef, Input, OnChanges, OnDestroy, ViewChild } from '@angular/core';
import * as echarts from 'echarts/core';
import { BarChart, LineChart } from 'echarts/charts';
import { AriaComponent, GridComponent, LegendComponent, TitleComponent, TooltipComponent } from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';

echarts.use([AriaComponent, BarChart, GridComponent, LegendComponent, LineChart, SVGRenderer, TitleComponent, TooltipComponent]);

export interface ChartSeries { name: string; values: Array<number | null>; }
export interface ChartSpec {
  type: 'line' | 'bar';
  title: string;
  x: string[];
  series: ChartSeries[];
  source_rows: number;
  truncated: boolean;
}

export function chartOptions(chart: ChartSpec): EChartsOption {
  return {
    animation: false,
    aria: { enabled: true },
    grid: { top: 54, right: 20, bottom: 58, left: 52 },
    legend: { bottom: 8, type: 'scroll' },
    title: { left: 0, text: chart.title, textStyle: { color: '#1c2942', fontSize: 14, fontWeight: 650 } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: chart.x, axisLabel: { hideOverlap: true, rotate: chart.x.length > 10 ? 32 : 0 } },
    yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: '#edf0f5' } } },
    series: chart.series.map(series => ({
      name: series.name,
      type: chart.type,
      data: series.values,
      barMaxWidth: 44,
      connectNulls: false,
      emphasis: { focus: 'series' },
      smooth: chart.type === 'line',
    })),
  };
}

export function chartMarkdown(chart: ChartSpec): string {
  const rows = chart.x.map((label, index) => [label, ...chart.series.map(series => series.values[index] ?? '')]);
  return [
    '', `### График: ${chart.title}`, '',
    `Тип: ${chart.type === 'line' ? 'линейный' : 'столбчатый'}; строк источника: ${chart.source_rows}.`, '',
    `| Категория | ${chart.series.map(series => series.name).join(' | ')} |`,
    `| --- | ${chart.series.map(() => '---:').join(' | ')} |`,
    ...rows.map(row => `| ${row.join(' | ')} |`),
    ...(chart.truncated ? ['', 'Показаны первые 24 точки.'] : []),
  ].join('\n');
}

@Component({
  selector: 'app-chart-evidence',
  template: '<div #host class="chart-host" role="img" [attr.aria-label]="chart.title"></div>',
  styles: [':host { display: block; margin-top: 12px; } .chart-host { height: 320px; min-width: 0; }'],
})
export class ChartEvidence implements AfterViewInit, OnChanges, OnDestroy {
  @Input({ required: true }) chart!: ChartSpec;
  @ViewChild('host') private host?: ElementRef<HTMLDivElement>;
  private instance?: echarts.ECharts;
  private resizeObserver?: ResizeObserver;

  ngAfterViewInit(): void {
    this.instance = echarts.init(this.host!.nativeElement, undefined, { renderer: 'svg' });
    this.resizeObserver = new ResizeObserver(() => this.instance?.resize());
    this.resizeObserver.observe(this.host!.nativeElement);
    this.render();
  }

  ngOnChanges(): void { this.render(); }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
    this.instance?.dispose();
  }

  private render(): void {
    this.instance?.setOption(chartOptions(this.chart), { notMerge: true, lazyUpdate: true });
  }
}
