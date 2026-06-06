import { colors, fonts } from "@/styles/global";
import Svg, { Circle, G } from "react-native-svg";
import { StyleSheet, Text, View } from "react-native";

type DonutChartProps = {
  percentage: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
  backgroundColor?: string;
  fontSize?: number;
};

export default function DonutChart({
  percentage,
  size = 82,
  strokeWidth = 9,
  color = colors.primary,
  backgroundColor = "#E8EAED",
  fontSize = 15,
}: DonutChartProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (Math.min(Math.max(percentage, 0), 100) / 100) * circumference;

  return (
    <View style={[styles.container, { width: size, height: size }]}>
      <Svg
        width={size}
        height={size}
        style={StyleSheet.absoluteFill}
      >
        <G rotation="-90" origin={`${size / 2}, ${size / 2}`}>
          {/* Track */}
          <Circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={backgroundColor}
            strokeWidth={strokeWidth}
            fill="none"
          />
          {/* Progress */}
          <Circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            fill="none"
            strokeDasharray={`${filled} ${circumference - filled}`}
            strokeLinecap="round"
          />
        </G>
      </Svg>
      <Text style={[styles.label, { fontSize }]}>{percentage}%</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
  },
  label: {
    fontFamily: fonts.heading,
    color: colors.text,
  },
});
