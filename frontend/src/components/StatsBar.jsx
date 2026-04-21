import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

function RiskGauge({ score }) {
  const data = [
    { value: score },
    { value: 100 - score },
  ];

  const getColor = (s) => {
    if (s >= 70) return '#ff3b5c';
    if (s >= 40) return '#ff7a3d';
    if (s >= 20) return '#ffc23d';
    return '#3ddc84';
  };

  const color = getColor(score);

  return (
    <div className="relative w-20 h-12">
      <ResponsiveContainer width="100%" height={48}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="100%"
            startAngle={180}
            endAngle={0}
            innerRadius={28}
            outerRadius={38}
            dataKey="value"
            stroke="none"
            animationBegin={200}
            animationDuration={1000}
          >
            <Cell fill={color} />
            <Cell fill="rgba(255,255,255,0.06)" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex items-end justify-center pb-0.5">
        <span className="text-sm font-bold" style={{ color }}>
          {score}
        </span>
      </div>
    </div>
  );
}

export default function StatsBar({ report }) {
  if (!report) return null;

  const stats = [
    {
      label: 'Functions Analyzed',
      value: report.functions_analyzed,
      icon: '⚙️',
      color: 'text-accent-blue',
    },
    {
      label: 'UB Bombs Detected',
      value: report.total_findings,
      icon: '💣',
      color: report.total_findings > 0 ? 'text-accent-red' : 'text-accent-green',
    },
    {
      label: 'Risk Score',
      value: null,
      icon: '📊',
      color: 'text-accent-yellow',
      custom: <RiskGauge score={report.risk_score} />,
    },
    {
      label: 'Risk Level',
      value: report.risk_level,
      icon: '🎯',
      color:
        report.risk_level === 'CRITICAL' ? 'text-accent-red' :
        report.risk_level === 'HIGH' ? 'text-accent-orange' :
        report.risk_level === 'MEDIUM' ? 'text-accent-yellow' :
        'text-accent-green',
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 px-6 py-4 stagger-children">
      {stats.map((stat) => (
        <div key={stat.label} className="glass-card p-4 flex items-center gap-3">
          <span className="text-2xl">{stat.icon}</span>
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wider truncate">
              {stat.label}
            </p>
            {stat.custom ? (
              stat.custom
            ) : (
              <p className={`text-2xl font-bold ${stat.color} tracking-tight`}>
                {stat.value}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
