import Svg, { Polyline } from "react-native-svg";
import { View } from "react-native";

type MiniLineChartProps = {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  strokeWidth?: number;
};

export default function MiniLineChart({
  data,
  width = 130,
  height = 48,
  color = "#4ADE80",
  strokeWidth = 2,
}: MiniLineChartProps) {
  if (!data || data.length < 2) return null;

  const maxVal = Math.max(...data);
  const minVal = Math.min(...data);
  const range = maxVal - minVal || 1;
  const pad = 3;

  const points = data
    .map((val, i) => {
      const x = pad + (i / (data.length - 1)) * (width - pad * 2);
      const y = pad + (1 - (val - minVal) / range) * (height - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <View>
      <Svg width={width} height={height}>
        <Polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </Svg>
    </View>
  );
}
