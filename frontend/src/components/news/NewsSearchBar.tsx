import { fonts } from "@/styles/global";
import { Search } from "lucide-react-native";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  TextInput,
  View,
} from "react-native";

const TEAL = "#0E4D53";

type Props = {
  value: string;
  onChangeText: (v: string) => void;
  onSubmit: () => void;
  loading?: boolean;
};

export default function NewsSearchBar({ value, onChangeText, onSubmit, loading }: Props) {
  return (
    <View style={styles.wrap}>
      <View style={styles.searchBox}>
        <TextInput
          value={value}
          onChangeText={onChangeText}
          placeholder="Search headlines..."
          placeholderTextColor="#9CA3AF"
          style={styles.searchInput}
          autoCorrect={false}
          autoCapitalize="none"
          returnKeyType="search"
          onSubmitEditing={onSubmit}
          editable={!loading}
        />
        <Pressable
          style={[styles.searchBtn, loading && styles.searchBtnDisabled]}
          onPress={onSubmit}
          disabled={loading}
          accessibilityLabel="Search news"
          hitSlop={8}
        >
          {loading ? (
            <ActivityIndicator size="small" color={TEAL} />
          ) : (
            <Search size={18} color={TEAL} strokeWidth={2} />
          )}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginBottom: 14,
  },
  searchBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    paddingLeft: 16,
    paddingRight: 6,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: "#E5EBED",
    gap: 8,
  },
  searchInput: {
    flex: 1,
    fontFamily: fonts.body,
    fontSize: 13,
    color: "#111827",
    paddingVertical: 8,
  },
  searchBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#F0F7F9",
    alignItems: "center",
    justifyContent: "center",
  },
  searchBtnDisabled: {
    opacity: 0.7,
  },
});
